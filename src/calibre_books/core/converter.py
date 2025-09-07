"""
Format conversion module for Calibre Books CLI.

This module provides functionality for converting book formats
using Calibre's conversion tools, with specialized support for KFX conversion.
"""

import logging
import subprocess
import time
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union

from ..utils.logging import LoggerMixin
from .book import BookFormat, ConversionResult

if TYPE_CHECKING:
    from ..config.manager import ConfigManager


class FormatConverter(LoggerMixin):
    """
    Book format converter.
    
    Provides methods for converting between various book formats
    using Calibre's conversion capabilities.
    """
    
    def __init__(self, config_manager: 'ConfigManager'):
        """
        Initialize format converter.
        
        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        super().__init__()
        self.config_manager = config_manager
        
        # Get conversion-specific configuration with error handling
        try:
            conversion_config = config_manager.get_conversion_config()
            self.max_parallel = conversion_config.get('max_parallel', 4)
            self.output_path = Path(conversion_config.get('output_path', '~/Converted-Books')).expanduser()
            self.kfx_plugin_required = conversion_config.get('kfx_plugin_required', True)
            
            self.logger.debug(f"Initialized FormatConverter with max_parallel: {self.max_parallel}, output: {self.output_path}")
        except Exception as e:
            self.logger.warning(f"Failed to load conversion config, using defaults: {e}")
            self.max_parallel = 4
            self.output_path = Path('~/Converted-Books').expanduser()
            self.kfx_plugin_required = True
        
        self.logger.info(f"Initialized format converter with output path: {self.output_path}")
    
    def check_system_requirements(self) -> Dict[str, bool]:
        """
        Check system requirements for conversion operations.
        
        Returns:
            Dict mapping requirement name to availability status
        """
        requirements = {}
        
        # Check Calibre tools
        try:
            subprocess.run(['calibre', '--version'], 
                         check=True, capture_output=True, timeout=10)
            requirements['calibre'] = True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            requirements['calibre'] = False
            
        try:
            subprocess.run(['ebook-convert', '--version'], 
                         check=True, capture_output=True, timeout=10)
            requirements['ebook-convert'] = True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            requirements['ebook-convert'] = False
            
        # Check KFX plugin
        requirements['kfx_plugin'] = self.validate_kfx_plugin()
        
        # Kindle Previewer is not required for basic conversion
        requirements['kindle_previewer'] = True
        
        return requirements

    def validate_kfx_plugin(self) -> bool:
        """Validate that KFX Output plugin is available in Calibre."""
        import subprocess
        import re
        
        self.logger.info("Validating KFX plugin availability")
        
        try:
            # Run calibre-customize to list plugins
            result = subprocess.run(
                ['calibre-customize', '-l'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                self.logger.error(f"Failed to list Calibre plugins: {result.stderr}")
                return False
            
            # Check for KFX Output plugin
            kfx_pattern = r'KFX Output.*Convert ebooks to KFX format'
            if re.search(kfx_pattern, result.stdout, re.IGNORECASE):
                self.logger.info("KFX Output plugin found and available")
                return True
            else:
                self.logger.warning("KFX Output plugin not found. Please install it via Calibre Preferences → Plugins")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout while checking Calibre plugins")
            return False
        except FileNotFoundError:
            self.logger.error("calibre-customize command not found. Please install Calibre CLI tools")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error checking KFX plugin: {e}")
            return False
    
    def convert_kfx_batch(
        self,
        kfx_files: List[Path],
        output_dir: Optional[Path] = None,
        output_format: str = "epub",
        parallel: int = 4,
        quality: str = "high",
        preserve_metadata: bool = True,
        progress_callback=None,
        dry_run: bool = False,
    ) -> List[ConversionResult]:
        """Convert multiple KFX files to another format with KFX-specific handling.
        
        This method provides specialized handling for KFX files, including:
        - KFX plugin validation before processing
        - KFX-specific conversion options
        - Enhanced error handling for KFX plugin issues
        
        Args:
            kfx_files: List of KFX files to convert
            output_dir: Output directory for converted files
            output_format: Target format for conversion
            parallel: Number of parallel conversion processes
            quality: Conversion quality setting
            preserve_metadata: Whether to preserve metadata
            progress_callback: Progress callback function
            dry_run: If True, only validate without converting
            
        Returns:
            List of conversion results
        """
        if not kfx_files:
            self.logger.warning("No KFX files provided for batch conversion")
            return []
        
        self.logger.info(f"Starting batch KFX conversion of {len(kfx_files)} files to {output_format}")
        
        # Pre-flight checks for KFX conversion
        if self.kfx_plugin_required and not self.validate_kfx_plugin():
            error_msg = "KFX Output plugin is required but not available. Please install the KFX plugin."
            self.logger.error(error_msg)
            
            # Return error results for all files
            return [
                ConversionResult(
                    input_file=kfx_file,
                    output_file=None,
                    input_format=BookFormat.KFX,
                    output_format=BookFormat(output_format.lower()),
                    success=False,
                    error=error_msg
                ) for kfx_file in kfx_files
            ]
        
        # Filter to only actual KFX files
        actual_kfx_files = []
        non_kfx_results = []
        
        for file_path in kfx_files:
            detected_format = self._detect_format(file_path)
            if detected_format == BookFormat.KFX:
                actual_kfx_files.append(file_path)
            else:
                # File is not actually KFX format
                non_kfx_results.append(ConversionResult(
                    input_file=file_path,
                    output_file=None,
                    input_format=detected_format or BookFormat.EPUB,
                    output_format=BookFormat(output_format.lower()),
                    success=False,
                    error=f"File is not KFX format (detected: {detected_format.value if detected_format else 'unknown'})"
                ))
        
        if not actual_kfx_files:
            self.logger.warning("No actual KFX files found in provided list")
            return non_kfx_results
        
        self.logger.info(f"Found {len(actual_kfx_files)} actual KFX files out of {len(kfx_files)} provided")
        
        # Use configured output directory if not specified
        if output_dir is None:
            output_dir = self.output_path
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Limit parallel workers to configured maximum
        parallel = min(parallel, self.max_parallel)
        
        if dry_run:
            self.logger.info("DRY RUN: KFX batch conversion preview")
            kfx_results = []
            for kfx_file in actual_kfx_files:
                # Generate expected output filename
                output_file = output_dir / f"{kfx_file.stem}_from_kfx.{output_format.lower()}"
                
                result = ConversionResult(
                    input_file=kfx_file,
                    output_file=output_file,
                    input_format=BookFormat.KFX,
                    output_format=BookFormat(output_format.lower()),
                    success=True,
                    conversion_time=0.0,
                    file_size_before=kfx_file.stat().st_size if kfx_file.exists() else 0,
                    file_size_after=kfx_file.stat().st_size if kfx_file.exists() else 0  # Estimate
                )
                kfx_results.append(result)
                
                if progress_callback:
                    progress_callback(len(kfx_results) / len(actual_kfx_files), 
                                    f"KFX Preview {len(kfx_results)}/{len(actual_kfx_files)}")
            
            return non_kfx_results + kfx_results
        
        # Prepare KFX conversion jobs with special naming
        conversion_jobs = []
        for kfx_file in actual_kfx_files:
            # Use special naming for KFX conversions to avoid conflicts
            output_file = output_dir / f"{kfx_file.stem}_from_kfx.{output_format.lower()}"
            
            # Skip if output already exists
            if output_file.exists():
                self.logger.info(f"Skipping {kfx_file.name} - output already exists: {output_file.name}")
                continue
            
            conversion_jobs.append({
                'input_file': kfx_file,
                'output_file': output_file,
                'output_format': output_format,
                'quality': quality,
                'preserve_metadata': preserve_metadata
            })
        
        if not conversion_jobs:
            self.logger.info("No KFX files need conversion (all outputs already exist)")
            return non_kfx_results
        
        self.logger.info(f"Processing {len(conversion_jobs)} KFX conversion jobs with {parallel} workers")
        
        results = []
        completed = 0
        
        def convert_kfx_job(job):
            """Helper function to convert a single KFX job with enhanced options"""
            return self.convert_single(
                input_file=job['input_file'],
                output_file=job['output_file'],
                output_format=job['output_format'],
                quality=job['quality'],
                include_cover=True,  # Always include cover for KFX
                preserve_metadata=job['preserve_metadata']
            )
        
        # Execute KFX conversions in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all KFX jobs
            future_to_job = {
                executor.submit(convert_kfx_job, job): job 
                for job in conversion_jobs
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # Progress reporting
                    if progress_callback:
                        progress_percentage = completed / len(conversion_jobs)
                        status_msg = f"KFX Converted {completed}/{len(conversion_jobs)}"
                        if result.success:
                            status_msg += f" - ✓ {result.input_file.name}"
                        else:
                            status_msg += f" - ✗ {result.input_file.name}"
                        progress_callback(progress_percentage, status_msg)
                    
                    # Log individual results with KFX-specific info
                    if result.success:
                        size_mb = result.file_size_after / 1024 / 1024 if result.file_size_after else 0
                        self.logger.info(f"✓ Converted KFX {result.input_file.name} to {output_format.upper()} ({size_mb:.1f} MB)")
                    else:
                        self.logger.error(f"✗ Failed to convert KFX {result.input_file.name}: {result.error}")
                        
                        # Provide KFX-specific error guidance
                        if "plugin" in result.error.lower() or "kfx" in result.error.lower():
                            self.logger.error("  💡 Try installing/updating the KFX Output plugin: calibre-customize -a KFXOutput.zip")
                        
                except Exception as exc:
                    # Handle unexpected exceptions with KFX context
                    error_result = ConversionResult(
                        input_file=job['input_file'],
                        output_file=job['output_file'],
                        input_format=BookFormat.KFX,
                        output_format=BookFormat(output_format.lower()),
                        success=False,
                        error=f"Unexpected KFX conversion error: {str(exc)}"
                    )
                    results.append(error_result)
                    completed += 1
                    
                    self.logger.error(f"✗ Exception converting KFX {job['input_file'].name}: {exc}")
                    
                    if progress_callback:
                        progress_percentage = completed / len(conversion_jobs)
                        progress_callback(progress_percentage, f"KFX Error {completed}/{len(conversion_jobs)}")
        
        # Combine results from non-KFX files and KFX conversions
        all_results = non_kfx_results + results
        
        # Summary statistics for KFX conversion
        kfx_successful = [r for r in results if r.success]
        kfx_failed = [r for r in results if not r.success]
        
        if results:  # Only log KFX summary if we actually converted KFX files
            total_kfx_size_before = sum(r.file_size_before or 0 for r in results) / 1024 / 1024
            total_kfx_size_after = sum(r.file_size_after or 0 for r in kfx_successful) / 1024 / 1024
            total_kfx_time = sum(r.conversion_time or 0 for r in results)
            
            self.logger.info(f"KFX batch conversion completed:")
            self.logger.info(f"  ✓ Successful KFX conversions: {len(kfx_successful)}")
            self.logger.info(f"  ✗ Failed KFX conversions: {len(kfx_failed)}")
            self.logger.info(f"  📊 Total KFX input size: {total_kfx_size_before:.1f} MB")
            self.logger.info(f"  📊 Total KFX output size: {total_kfx_size_after:.1f} MB")
            self.logger.info(f"  ⏱️ Total KFX time: {total_kfx_time:.1f} seconds")
            
            if kfx_failed:
                self.logger.warning(f"Failed KFX conversions:")
                for fail in kfx_failed[:3]:  # Show first 3 failures
                    self.logger.warning(f"  ✗ {fail.input_file.name}: {fail.error}")
                if len(kfx_failed) > 3:
                    self.logger.warning(f"  ... and {len(kfx_failed) - 3} more KFX failures")
        
        return all_results
    
    def convert_single(
        self,
        input_file: Path,
        output_file: Optional[Path] = None,
        output_format: str = "epub",
        quality: str = "high",
        include_cover: bool = True,
        preserve_metadata: bool = True,
        progress_callback=None,
        dry_run: bool = False,
    ) -> ConversionResult:
        """Convert a single book file to another format using Calibre ebook-convert.
        
        Args:
            input_file: Path to input book file
            output_file: Path for output file (auto-generated if None)
            output_format: Target format (epub, mobi, pdf, etc.)
            quality: Conversion quality setting (high, medium, low)
            include_cover: Whether to include cover in conversion
            preserve_metadata: Whether to preserve metadata during conversion
            progress_callback: Optional progress callback function
            dry_run: If True, only validate without actually converting
            
        Returns:
            ConversionResult with success status and details
        """
        start_time = time.time()
        self.logger.info(f"Converting {input_file} to {output_format}")
        
        # Validate input file
        if not input_file.exists():
            error_msg = f"Input file does not exist: {input_file}"
            self.logger.error(error_msg)
            return ConversionResult(
                input_file=input_file,
                output_file=None,
                input_format=self._detect_format(input_file),
                output_format=BookFormat(output_format.lower()),
                success=False,
                error=error_msg
            )
        
        if not input_file.is_file():
            error_msg = f"Input path is not a file: {input_file}"
            self.logger.error(error_msg)
            return ConversionResult(
                input_file=input_file,
                output_file=None,
                input_format=self._detect_format(input_file),
                output_format=BookFormat(output_format.lower()),
                success=False,
                error=error_msg
            )
        
        # Detect input format
        input_format = self._detect_format(input_file)
        if input_format is None:
            error_msg = f"Unsupported input format: {input_file.suffix}"
            self.logger.error(error_msg)
            return ConversionResult(
                input_file=input_file,
                output_file=None,
                input_format=BookFormat.EPUB,  # Fallback
                output_format=BookFormat(output_format.lower()),
                success=False,
                error=error_msg
            )
        
        # Generate output file path if not provided
        if output_file is None:
            output_file = self.output_path / f"{input_file.stem}.{output_format.lower()}"
            
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Get file sizes for comparison
        file_size_before = input_file.stat().st_size
        
        if dry_run:
            self.logger.info(f"DRY RUN: Would convert {input_file} to {output_file}")
            return ConversionResult(
                input_file=input_file,
                output_file=output_file,
                input_format=input_format,
                output_format=BookFormat(output_format.lower()),
                success=True,
                conversion_time=0.0,
                file_size_before=file_size_before,
                file_size_after=file_size_before  # Estimate same size for dry run
            )
        
        try:
            # Build ebook-convert command
            cmd = self._build_conversion_command(
                input_file=input_file,
                output_file=output_file,
                output_format=output_format,
                quality=quality,
                include_cover=include_cover,
                preserve_metadata=preserve_metadata
            )
            
            self.logger.debug(f"Running conversion command: {' '.join(str(x) for x in cmd)}")
            
            # Execute conversion
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout for single file conversion
            )
            
            conversion_time = time.time() - start_time
            
            if result.returncode == 0:
                # Verify output file was created
                if output_file.exists():
                    file_size_after = output_file.stat().st_size
                    self.logger.info(f"Successfully converted {input_file.name} to {output_format} ({file_size_after / 1024 / 1024:.1f} MB)")
                    
                    if progress_callback:
                        progress_callback(1.0, "Conversion completed")
                    
                    return ConversionResult(
                        input_file=input_file,
                        output_file=output_file,
                        input_format=input_format,
                        output_format=BookFormat(output_format.lower()),
                        success=True,
                        conversion_time=conversion_time,
                        file_size_before=file_size_before,
                        file_size_after=file_size_after
                    )
                else:
                    error_msg = "Conversion completed but output file was not created"
                    self.logger.error(error_msg)
                    return ConversionResult(
                        input_file=input_file,
                        output_file=output_file,
                        input_format=input_format,
                        output_format=BookFormat(output_format.lower()),
                        success=False,
                        error=error_msg,
                        conversion_time=conversion_time,
                        file_size_before=file_size_before
                    )
            else:
                # Conversion failed
                error_msg = result.stderr.strip() if result.stderr else "Unknown conversion error"
                self.logger.error(f"Conversion failed for {input_file.name}: {error_msg}")
                return ConversionResult(
                    input_file=input_file,
                    output_file=output_file,
                    input_format=input_format,
                    output_format=BookFormat(output_format.lower()),
                    success=False,
                    error=error_msg,
                    conversion_time=conversion_time,
                    file_size_before=file_size_before
                )
                
        except subprocess.TimeoutExpired:
            error_msg = f"Conversion timeout (600s exceeded) for {input_file.name}"
            self.logger.error(error_msg)
            return ConversionResult(
                input_file=input_file,
                output_file=output_file,
                input_format=input_format,
                output_format=BookFormat(output_format.lower()),
                success=False,
                error=error_msg,
                conversion_time=time.time() - start_time,
                file_size_before=file_size_before
            )
        except Exception as e:
            error_msg = f"Unexpected error during conversion: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(
                input_file=input_file,
                output_file=output_file,
                input_format=input_format,
                output_format=BookFormat(output_format.lower()),
                success=False,
                error=error_msg,
                conversion_time=time.time() - start_time,
                file_size_before=file_size_before
            )
    
    def convert_batch(
        self,
        files: List[Path],
        output_dir: Optional[Path] = None,
        output_format: str = "epub",
        parallel: int = 2,
        quality: str = "high",
        include_cover: bool = True,
        preserve_metadata: bool = True,
        progress_callback=None,
        dry_run: bool = False,
    ) -> List[ConversionResult]:
        """Convert multiple files in batch with parallel processing.
        
        Args:
            files: List of input files to convert
            output_dir: Output directory (uses config default if None)
            output_format: Target format for conversion
            parallel: Number of parallel conversion processes
            quality: Conversion quality setting
            include_cover: Whether to include covers
            preserve_metadata: Whether to preserve metadata
            progress_callback: Progress callback function
            dry_run: If True, only validate without converting
            
        Returns:
            List of ConversionResult objects
        """
        if not files:
            self.logger.warning("No files provided for batch conversion")
            return []
        
        # Use configured output directory if not specified
        if output_dir is None:
            output_dir = self.output_path
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Limit parallel workers to configured maximum
        parallel = min(parallel, self.max_parallel)
        
        self.logger.info(f"Starting batch conversion of {len(files)} files to {output_format} (parallel: {parallel})")
        
        if dry_run:
            self.logger.info("DRY RUN: Batch conversion preview")
            results = []
            for file_path in files:
                result = self.convert_single(
                    input_file=file_path,
                    output_file=output_dir / f"{file_path.stem}.{output_format.lower()}",
                    output_format=output_format,
                    quality=quality,
                    include_cover=include_cover,
                    preserve_metadata=preserve_metadata,
                    dry_run=True
                )
                results.append(result)
                if progress_callback:
                    progress_callback(len(results) / len(files), f"Preview {len(results)}/{len(files)}")
            return results
        
        # Prepare conversion jobs
        conversion_jobs = []
        for file_path in files:
            output_file = output_dir / f"{file_path.stem}.{output_format.lower()}"
            
            # Skip if output already exists (unless force conversion is enabled)
            if output_file.exists():
                self.logger.info(f"Skipping {file_path.name} - output already exists: {output_file.name}")
                continue
            
            conversion_jobs.append({
                'input_file': file_path,
                'output_file': output_file,
                'output_format': output_format,
                'quality': quality,
                'include_cover': include_cover,
                'preserve_metadata': preserve_metadata
            })
        
        if not conversion_jobs:
            self.logger.info("No files need conversion (all outputs already exist)")
            return []
        
        self.logger.info(f"Processing {len(conversion_jobs)} conversion jobs with {parallel} workers")
        
        results = []
        completed = 0
        
        def convert_single_job(job):
            """Helper function to convert a single job"""
            return self.convert_single(
                input_file=job['input_file'],
                output_file=job['output_file'],
                output_format=job['output_format'],
                quality=job['quality'],
                include_cover=job['include_cover'],
                preserve_metadata=job['preserve_metadata']
            )
        
        # Execute conversions in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(convert_single_job, job): job 
                for job in conversion_jobs
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    
                    # Progress reporting
                    if progress_callback:
                        progress_percentage = completed / len(conversion_jobs)
                        status_msg = f"Converted {completed}/{len(conversion_jobs)}"
                        if result.success:
                            status_msg += f" - ✓ {result.input_file.name}"
                        else:
                            status_msg += f" - ✗ {result.input_file.name}"
                        progress_callback(progress_percentage, status_msg)
                    
                    # Log individual results
                    if result.success:
                        size_mb = result.file_size_after / 1024 / 1024 if result.file_size_after else 0
                        self.logger.info(f"✓ Converted {result.input_file.name} ({size_mb:.1f} MB)")
                    else:
                        self.logger.error(f"✗ Failed to convert {result.input_file.name}: {result.error}")
                        
                except Exception as exc:
                    # Handle unexpected exceptions
                    error_result = ConversionResult(
                        input_file=job['input_file'],
                        output_file=job['output_file'],
                        input_format=self._detect_format(job['input_file']) or BookFormat.EPUB,
                        output_format=BookFormat(output_format.lower()),
                        success=False,
                        error=f"Unexpected error: {str(exc)}"
                    )
                    results.append(error_result)
                    completed += 1
                    
                    self.logger.error(f"✗ Exception converting {job['input_file'].name}: {exc}")
                    
                    if progress_callback:
                        progress_percentage = completed / len(conversion_jobs)
                        progress_callback(progress_percentage, f"Error {completed}/{len(conversion_jobs)}")
        
        # Summary statistics
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        total_size_before = sum(r.file_size_before or 0 for r in results) / 1024 / 1024
        total_size_after = sum(r.file_size_after or 0 for r in successful) / 1024 / 1024
        total_time = sum(r.conversion_time or 0 for r in results)
        
        self.logger.info(f"Batch conversion completed:")
        self.logger.info(f"  ✓ Successful: {len(successful)}")
        self.logger.info(f"  ✗ Failed: {len(failed)}")
        self.logger.info(f"  📊 Total input size: {total_size_before:.1f} MB")
        self.logger.info(f"  📊 Total output size: {total_size_after:.1f} MB")
        self.logger.info(f"  ⏱️ Total time: {total_time:.1f} seconds")
        
        if failed:
            self.logger.warning(f"Failed conversions:")
            for fail in failed[:5]:  # Show first 5 failures
                self.logger.warning(f"  ✗ {fail.input_file.name}: {fail.error}")
            if len(failed) > 5:
                self.logger.warning(f"  ... and {len(failed) - 5} more failures")
        
        return results
    
    def find_convertible_files(
        self,
        input_dir: Path,
        source_format: Optional[str] = None,
        recursive: bool = False,
        progress_callback=None,
    ) -> List[Path]:
        """Find convertible files in directory with format filtering.
        
        Args:
            input_dir: Directory to search in
            source_format: Filter by specific source format (e.g., 'mobi', 'epub')
            recursive: Whether to search subdirectories recursively
            progress_callback: Optional progress callback for large directories
            
        Returns:
            List of paths to convertible book files, sorted by name
        """
        self.logger.info(f"Finding convertible files in {input_dir} (recursive: {recursive})")
        
        if not input_dir.exists():
            self.logger.error(f"Input directory does not exist: {input_dir}")
            return []
        
        if not input_dir.is_dir():
            self.logger.error(f"Input path is not a directory: {input_dir}")
            return []
        
        # Get supported input formats
        try:
            supported_formats = self.get_supported_formats()
            supported_extensions = {fmt.extension.lower().lstrip('.') for fmt in supported_formats.input_formats}
        except Exception as e:
            self.logger.warning(f"Failed to get supported formats, using defaults: {e}")
            supported_extensions = {'epub', 'mobi', 'azw', 'azw3', 'pdf', 'txt', 'html', 'rtf', 'docx', 'fb2', 'lit', 'pdb'}
        
        # If source_format is specified, filter to only that format
        if source_format:
            source_ext = source_format.lower().lstrip('.')
            if source_ext in supported_extensions:
                supported_extensions = {source_ext}
            else:
                self.logger.warning(f"Unsupported source format: {source_format}")
                return []
        
        convertible_files = []
        total_checked = 0
        
        try:
            # Use appropriate iteration method based on recursive flag
            if recursive:
                file_iterator = input_dir.rglob('*')
            else:
                file_iterator = input_dir.iterdir()
            
            for file_path in file_iterator:
                total_checked += 1
                
                # Progress reporting every 100 files
                if progress_callback and total_checked % 100 == 0:
                    progress_callback(f"Scanned {total_checked} files, found {len(convertible_files)} convertible")
                
                # Skip directories and non-files
                if not file_path.is_file():
                    continue
                
                # Check file extension
                extension = file_path.suffix.lower().lstrip('.')
                if extension in supported_extensions:
                    # Skip files that look like conversion outputs to avoid duplicates
                    if '_kfx' not in file_path.stem.lower() and '_converted' not in file_path.stem.lower():
                        convertible_files.append(file_path)
                        self.logger.debug(f"Found convertible file: {file_path}")
        
        except Exception as e:
            self.logger.error(f"Error scanning directory {input_dir}: {e}")
            return convertible_files  # Return what we found so far
        
        # Sort files by name for predictable order
        convertible_files.sort(key=lambda p: p.name.lower())
        
        self.logger.info(f"Found {len(convertible_files)} convertible files in {input_dir}")
        
        if progress_callback:
            progress_callback(f"Found {len(convertible_files)} convertible files")
        
        return convertible_files
    
    def get_supported_formats(self):
        """Get supported input and output formats dynamically from Calibre.
        
        Returns:
            SupportedFormats object with actual Calibre-supported formats
        """
        from dataclasses import dataclass
        
        @dataclass
        class Format:
            name: str
            extension: str
            description: str
        
        @dataclass
        class SupportedFormats:
            input_formats: List[Format]
            output_formats: List[Format]
        
        # Try to get actual supported formats from Calibre
        try:
            input_formats, output_formats = self._query_calibre_formats()
            return SupportedFormats(
                input_formats=input_formats,
                output_formats=output_formats
            )
        except Exception as e:
            self.logger.warning(f"Failed to query Calibre formats dynamically, using defaults: {e}")
            
        # Fallback to static format list if dynamic detection fails
        input_formats = [
            Format("MOBI", ".mobi", "Amazon Kindle format"),
            Format("EPUB", ".epub", "Standard e-book format"),
            Format("PDF", ".pdf", "Portable Document Format"),
            Format("AZW", ".azw", "Amazon Kindle format (old)"),
            Format("AZW3", ".azw3", "Amazon Kindle format"),
            Format("KFX", ".kfx", "Amazon Kindle format (newer)"),
            Format("TXT", ".txt", "Plain text format"),
            Format("RTF", ".rtf", "Rich Text Format"),
            Format("HTML", ".html", "HyperText Markup Language"),
            Format("DOCX", ".docx", "Microsoft Word format"),
            Format("FB2", ".fb2", "FictionBook format"),
            Format("LIT", ".lit", "Microsoft Reader format"),
            Format("PDB", ".pdb", "Palm Database format"),
        ]
        
        output_formats = [
            Format("EPUB", ".epub", "Standard e-book format"),
            Format("MOBI", ".mobi", "Amazon Kindle format"),
            Format("AZW3", ".azw3", "Amazon Kindle format"),
            Format("PDF", ".pdf", "Portable Document Format"),
            Format("TXT", ".txt", "Plain text format"),
            Format("RTF", ".rtf", "Rich Text Format"),
            Format("HTML", ".html", "HyperText Markup Language"),
            Format("DOCX", ".docx", "Microsoft Word format"),
            Format("FB2", ".fb2", "FictionBook format"),
        ]
        
        return SupportedFormats(
            input_formats=input_formats,
            output_formats=output_formats
        )
    
    def _detect_format(self, file_path: Path) -> Optional[BookFormat]:
        """Detect book format from file extension.
        
        Args:
            file_path: Path to the book file
            
        Returns:
            BookFormat enum value or None if unsupported
        """
        extension = file_path.suffix.lower().lstrip('.')
        
        format_mapping = {
            'mobi': BookFormat.MOBI,
            'epub': BookFormat.EPUB,
            'pdf': BookFormat.PDF,
            'azw': BookFormat.AZW,
            'azw3': BookFormat.AZW3,
            'kfx': BookFormat.KFX,
            'txt': BookFormat.TXT,
            'rtf': BookFormat.RTF,
            'html': BookFormat.HTML,
            'htm': BookFormat.HTML,
            'docx': BookFormat.DOCX,
            'fb2': BookFormat.FB2,
            'lit': BookFormat.LIT,
            'pdb': BookFormat.PDB,
        }
        
        return format_mapping.get(extension)
    
    def _build_conversion_command(
        self,
        input_file: Path,
        output_file: Path,
        output_format: str,
        quality: str = "high",
        include_cover: bool = True,
        preserve_metadata: bool = True,
    ) -> List[Union[str, Path]]:
        """Build ebook-convert command with appropriate options.
        
        Args:
            input_file: Path to input file
            output_file: Path to output file
            output_format: Target format
            quality: Conversion quality setting
            include_cover: Whether to include cover
            preserve_metadata: Whether to preserve metadata
            
        Returns:
            Command as list of strings/paths
        """
        cmd = ['ebook-convert', str(input_file), str(output_file)]
        
        # Add format-specific options based on output format
        if output_format.lower() == 'kfx':
            # KFX-specific options adapted from legacy converter
            kfx_options = {
                'output-profile': 'kindle_fire',
                'no-inline-toc': True,
                'margin-left': '5',
                'margin-right': '5',
                'margin-top': '5',
                'margin-bottom': '5',
                'change-justification': 'left',
                'remove-paragraph-spacing': True,
                'remove-paragraph-spacing-indent-size': '1.5',
                'insert-blank-line': True,
                'insert-blank-line-size': '0.5'
            }
            
            # Enhanced KFX options if plugin available
            if self.validate_kfx_plugin():
                kfx_options.update({
                    'enable-heuristics': True,
                    'markup-chapter-headings': True,
                    'remove-fake-margins': True
                })
            
            # Add KFX options to command
            for key, value in kfx_options.items():
                if isinstance(value, bool):
                    if value:
                        cmd.append(f'--{key}')
                else:
                    cmd.extend([f'--{key}', str(value)])
        
        elif output_format.lower() in ['epub', 'mobi', 'azw3']:
            # Standard e-book format options
            if quality == "high":
                cmd.extend([
                    '--preserve-cover-aspect-ratio',
                    '--embed-all-fonts',
                    '--subset-embedded-fonts'
                ])
            
            if include_cover:
                cmd.append('--preserve-cover-aspect-ratio')
            else:
                cmd.append('--no-default-epub-cover')
        
        elif output_format.lower() == 'pdf':
            # PDF-specific options
            cmd.extend([
                '--paper-size', 'a4',
                '--pdf-default-font-size', '12',
                '--pdf-mono-font-size', '10'
            ])
        
        # Common options for all formats
        if preserve_metadata:
            cmd.append('--preserve-metadata')
        
        # Quality-based options
        if quality == "high":
            cmd.extend(['--extra-css', 'body { text-align: justify; }'])
        elif quality == "low":
            cmd.extend(['--compress-images', '--jpeg-quality', '60'])
        
        return cmd
    
    def _query_calibre_formats(self) -> tuple[List, List]:
        """Query Calibre for supported input and output formats.
        
        Returns:
            Tuple of (input_formats, output_formats) lists
        """
        from dataclasses import dataclass
        
        @dataclass
        class Format:
            name: str
            extension: str
            description: str
        
        input_formats = []
        output_formats = []
        
        try:
            # Query ebook-convert help to get supported formats
            result = subprocess.run(
                ['ebook-convert', '--help'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse the help output to extract format information
                # This is a simplified implementation - could be enhanced
                help_text = result.stdout
                
                # Look for input formats section
                if "Input Formats:" in help_text:
                    # Extract formats from help text (this would need more sophisticated parsing)
                    pass
                
                # For now, return the static list with confidence that Calibre is available
                input_formats = [
                    Format("EPUB", ".epub", "Standard e-book format"),
                    Format("MOBI", ".mobi", "Amazon Kindle format"),
                    Format("AZW", ".azw", "Amazon Kindle format"),
                    Format("AZW3", ".azw3", "Amazon Kindle format"),
                    Format("PDF", ".pdf", "Portable Document Format"),
                    Format("TXT", ".txt", "Plain text format"),
                    Format("HTML", ".html", "HyperText Markup Language"),
                    Format("DOCX", ".docx", "Microsoft Word format"),
                    Format("RTF", ".rtf", "Rich Text Format"),
                    Format("FB2", ".fb2", "FictionBook format"),
                ]
                
                output_formats = [
                    Format("EPUB", ".epub", "Standard e-book format"),
                    Format("MOBI", ".mobi", "Amazon Kindle format"),
                    Format("AZW3", ".azw3", "Amazon Kindle format"),
                    Format("PDF", ".pdf", "Portable Document Format"),
                    Format("TXT", ".txt", "Plain text format"),
                    Format("HTML", ".html", "HyperText Markup Language"),
                    Format("RTF", ".rtf", "Rich Text Format"),
                ]
        
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.error(f"Failed to query Calibre formats: {e}")
            raise
        
        return input_formats, output_formats