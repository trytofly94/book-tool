"""
KFX Conversion module for Calibre Books CLI.

This module provides specialized KFX conversion functionality that extends
the base FormatConverter with KFX-specific features and optimizations.
"""

import subprocess
import os
import time
import concurrent.futures
from pathlib import Path
from threading import Lock
from typing import List, Optional, Dict, TYPE_CHECKING, Union

from ...utils.logging import LoggerMixin
from ..book import Book, BookFormat, ConversionResult
from ..converter import FormatConverter

if TYPE_CHECKING:
    from ...config.manager import ConfigManager


class KFXConverter(LoggerMixin):
    """
    Specialized KFX converter with CLI integration.

    This class provides enhanced KFX conversion capabilities by wrapping
    the FormatConverter with KFX-specific features like:
    - Advanced KFX plugin detection and validation
    - KFX-specific conversion options and profiles
    - Calibre library integration
    - Comprehensive error handling for KFX workflows
    """

    def __init__(self, config_manager: "ConfigManager"):
        """
        Initialize KFX converter with ConfigManager integration.

        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        super().__init__()
        self.config_manager = config_manager
        self._conversion_lock = Lock()

        # Initialize base format converter for delegation
        self._format_converter = FormatConverter(config_manager)

        # Load KFX-specific configuration
        self._load_kfx_config()

        self.logger.info(
            f"Initialized KFXConverter with max_workers: {self.max_workers}"
        )

    def _load_kfx_config(self):
        """Load KFX-specific configuration from ConfigManager."""
        try:
            # Load conversion configuration
            conversion_config = self.config_manager.get_conversion_config()
            self.max_workers = conversion_config.get("max_parallel", 4)
            self.output_path = Path(
                conversion_config.get("output_path", "~/Converted-Books")
            ).expanduser()
            self.kfx_plugin_required = conversion_config.get(
                "kfx_plugin_required", True
            )

            # Load Calibre configuration
            self.calibre_config = self.config_manager.get_calibre_config()
            self.library_path = self.calibre_config.get("library_path")
            if self.library_path:
                self.library_path = Path(self.library_path).expanduser()

            self.logger.debug(
                f"Loaded KFX config: workers={self.max_workers}, "
                f"output={self.output_path}, library={self.library_path}"
            )

        except Exception as e:
            self.logger.warning(
                f"Failed to load KFX configuration, using defaults: {e}"
            )
            # Fallback to defaults
            self.max_workers = 4
            self.output_path = Path("~/Converted-Books").expanduser()
            self.kfx_plugin_required = True
            self.calibre_config = {}
            self.library_path = None

    @property
    def config_manager(self) -> "ConfigManager":
        """Access to the ConfigManager instance (for test compatibility)."""
        return self._config_manager

    @config_manager.setter
    def config_manager(self, value: "ConfigManager"):
        """Set the ConfigManager instance."""
        self._config_manager = value

    def check_system_requirements(self) -> Dict[str, bool]:
        """
        Check system requirements for KFX conversion operations.

        Extends the base FormatConverter requirements with KFX-specific checks.

        Returns:
            Dict mapping requirement name to availability status
        """
        # Start with base system requirements
        requirements = self._format_converter.check_system_requirements()

        # Add KFX-specific requirements
        requirements.update(
            {
                "kfx_plugin_advanced": self._check_advanced_kfx_plugin(),
                "kindle_previewer": self._check_kindle_previewer(),
                "library_access": self._check_library_access(),
            }
        )

        return requirements

    def _check_advanced_kfx_plugin(self) -> bool:
        """Advanced KFX plugin detection with detailed validation."""
        try:
            # Use the base converter's validation as starting point
            if not self._format_converter.validate_kfx_plugin():
                return False

            # Additional KFX plugin validation
            result = subprocess.run(
                ["calibre-customize", "-l"], capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0:
                return False

            # Check for specific KFX plugin features
            kfx_patterns = [
                r"KFX Output.*Convert ebooks to KFX format",
                r"KFXOutput.*KFX",
            ]

            for pattern in kfx_patterns:
                import re

                if re.search(pattern, result.stdout, re.IGNORECASE):
                    self.logger.info(
                        "Advanced KFX Output plugin validated successfully"
                    )
                    return True

            return False

        except Exception as e:
            self.logger.error(f"Advanced KFX plugin check failed: {e}")
            return False

    def _check_kindle_previewer(self) -> bool:
        """Check if Kindle Previewer 3 is available."""
        previewer_paths = [
            "/Applications/Kindle Previewer 3.app",  # macOS
            "/usr/local/bin/kindle-previewer",  # Linux
            "C:\\Program Files (x86)\\Amazon\\Kindle Previewer 3\\Kindle Previewer.exe",  # Windows
        ]

        for path in previewer_paths:
            if os.path.exists(path):
                self.logger.debug(f"Found Kindle Previewer at: {path}")
                return True

        return False

    def _check_library_access(self) -> bool:
        """Check if Calibre library is accessible."""
        if not self.library_path:
            return False

        try:
            return (
                self.library_path.exists()
                and self.library_path.is_dir()
                and (self.library_path / "metadata.db").exists()
            )
        except Exception as e:
            self.logger.error(f"Library access check failed: {e}")
            return False

    def convert_books_to_kfx(
        self,
        books: List[Book],
        output_dir: Optional[Path] = None,
        parallel: Optional[int] = None,
        quality: str = "high",
        preserve_metadata: bool = True,
        progress_callback=None,
        dry_run: bool = False,
    ) -> List[ConversionResult]:
        """
        Convert multiple books to KFX format with enhanced options.

        Args:
            books: List of Book objects to convert
            output_dir: Output directory (uses config default if None)
            parallel: Number of parallel workers (uses config default if None)
            quality: Conversion quality setting
            preserve_metadata: Whether to preserve metadata
            progress_callback: Progress callback function
            dry_run: If True, only validate without converting

        Returns:
            List of ConversionResult objects
        """
        if not books:
            self.logger.warning("No books provided for KFX conversion")
            return []

        # Validate that books have valid file paths
        valid_books = []
        invalid_results = []

        for book in books:
            if not book.file_path or not book.file_path.exists():
                error_msg = f"Source file not found: {book.file_path}"
                invalid_results.append(
                    ConversionResult(
                        input_file=(
                            book.file_path if book.file_path else Path("unknown")
                        ),
                        output_file=None,
                        input_format=(
                            book.metadata.format if book.metadata else BookFormat.EPUB
                        ),
                        output_format=BookFormat.KFX,
                        success=False,
                        error=error_msg,
                    )
                )
                self.logger.error(error_msg)
            else:
                valid_books.append(book)

        if not valid_books:
            self.logger.warning("No valid books found for conversion")
            return invalid_results

        # Extract file paths for FormatConverter
        kfx_files = [book.file_path for book in valid_books]

        # Use configured defaults if not specified
        if output_dir is None:
            output_dir = self.output_path
        if parallel is None:
            parallel = self.max_workers

        self.logger.info(
            f"Converting {len(valid_books)} books to KFX format "
            f"(parallel: {parallel}, quality: {quality})"
        )

        # Use the base converter's KFX batch conversion with enhanced options
        conversion_results = self._format_converter.convert_kfx_batch(
            kfx_files=kfx_files,
            output_dir=output_dir,
            output_format="kfx",  # Force KFX output
            parallel=parallel,
            quality=quality,
            preserve_metadata=preserve_metadata,
            progress_callback=progress_callback,
            dry_run=dry_run,
        )

        # Combine results from invalid books and successful conversions
        all_results = invalid_results + conversion_results

        # Enhanced logging for KFX conversion summary
        successful = [r for r in conversion_results if r.success]
        failed = [r for r in conversion_results if not r.success]

        self.logger.info("KFX conversion completed:")
        self.logger.info(f"  ✓ Successful: {len(successful)}")
        self.logger.info(f"  ✗ Failed: {len(failed) + len(invalid_results)}")

        if failed or invalid_results:
            self.logger.warning("Failed conversions:")
            for fail in (failed + invalid_results)[:3]:  # Show first 3
                file_name = fail.input_file.name if fail.input_file else "unknown"
                self.logger.warning(f"  ✗ {file_name}: {fail.error}")

            total_failures = len(failed) + len(invalid_results)
            if total_failures > 3:
                self.logger.warning(f"  ... and {total_failures - 3} more failures")

        return all_results

    def convert_single_to_kfx(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        conversion_options: Optional[Dict[str, Union[str, bool, int]]] = None,
        progress_callback=None,
        dry_run: bool = False,
    ) -> ConversionResult:
        """
        Convert a single file to KFX format with enhanced options.

        Args:
            input_path: Path to input book file
            output_path: Path for output file (auto-generated if None)
            conversion_options: Additional KFX-specific options
            progress_callback: Progress callback function
            dry_run: If True, only validate without converting

        Returns:
            ConversionResult with success status and details
        """
        start_time = time.time()

        # Validate input
        if not input_path.exists():
            error_msg = f"Input file does not exist: {input_path}"
            self.logger.error(error_msg)
            return ConversionResult(
                input_file=input_path,
                output_file=output_path,
                input_format=self._format_converter._detect_format(input_path)
                or BookFormat.EPUB,
                output_format=BookFormat.KFX,
                success=False,
                error=error_msg,
            )

        # Generate output path if not provided
        if output_path is None:
            output_path = self.output_path / f"{input_path.stem}_kfx.azw3"

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            self.logger.info(f"DRY RUN: Would convert {input_path} to {output_path}")
            return ConversionResult(
                input_file=input_path,
                output_file=output_path,
                input_format=self._format_converter._detect_format(input_path)
                or BookFormat.EPUB,
                output_format=BookFormat.KFX,
                success=True,
                conversion_time=0.0,
                file_size_before=input_path.stat().st_size,
                file_size_after=input_path.stat().st_size,  # Estimate
            )

        try:
            # Build enhanced KFX conversion command
            cmd = self._build_enhanced_kfx_command(
                input_path=input_path,
                output_path=output_path,
                conversion_options=conversion_options,
            )

            with self._conversion_lock:
                self.logger.info(f"Converting: {input_path.name} → KFX")

            self.logger.debug(f"KFX command: {' '.join(str(x) for x in cmd)}")

            # Execute conversion with timeout
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600  # 10 minute timeout
            )

            conversion_time = time.time() - start_time
            success = result.returncode == 0

            if success and output_path.exists():
                file_size_after = output_path.stat().st_size

                with self._conversion_lock:
                    self.logger.info(
                        f"✓ KFX conversion successful: {output_path.name} "
                        f"({file_size_after / 1024 / 1024:.1f} MB)"
                    )

                if progress_callback:
                    progress_callback(1.0, "KFX conversion completed")

                return ConversionResult(
                    input_file=input_path,
                    output_file=output_path,
                    input_format=self._format_converter._detect_format(input_path)
                    or BookFormat.EPUB,
                    output_format=BookFormat.KFX,
                    success=True,
                    conversion_time=conversion_time,
                    file_size_before=input_path.stat().st_size,
                    file_size_after=file_size_after,
                )
            else:
                error_msg = (
                    result.stderr.strip() if result.stderr else "KFX conversion failed"
                )

                with self._conversion_lock:
                    self.logger.error(f"✗ KFX conversion failed: {input_path.name}")
                    self.logger.error(f"  Error: {error_msg}")

                return ConversionResult(
                    input_file=input_path,
                    output_file=output_path,
                    input_format=self._format_converter._detect_format(input_path)
                    or BookFormat.EPUB,
                    output_format=BookFormat.KFX,
                    success=False,
                    error=error_msg,
                    conversion_time=conversion_time,
                    file_size_before=input_path.stat().st_size,
                )

        except subprocess.TimeoutExpired:
            error_msg = f"KFX conversion timeout (600s exceeded) for {input_path.name}"
            self.logger.error(error_msg)
            return ConversionResult(
                input_file=input_path,
                output_file=output_path,
                input_format=self._format_converter._detect_format(input_path)
                or BookFormat.EPUB,
                output_format=BookFormat.KFX,
                success=False,
                error=error_msg,
                conversion_time=time.time() - start_time,
                file_size_before=input_path.stat().st_size,
            )
        except Exception as e:
            error_msg = f"Unexpected KFX conversion error: {str(e)}"
            self.logger.error(error_msg)
            return ConversionResult(
                input_file=input_path,
                output_file=output_path,
                input_format=self._format_converter._detect_format(input_path)
                or BookFormat.EPUB,
                output_format=BookFormat.KFX,
                success=False,
                error=error_msg,
                conversion_time=time.time() - start_time,
                file_size_before=input_path.stat().st_size,
            )

    def _build_enhanced_kfx_command(
        self,
        input_path: Path,
        output_path: Path,
        conversion_options: Optional[Dict[str, Union[str, bool, int]]] = None,
    ) -> List[str]:
        """
        Build enhanced ebook-convert command with KFX-specific options.

        This method builds upon the FormatConverter's KFX options with
        additional enhancements from the legacy ParallelKFXConverter.

        Args:
            input_path: Path to input file
            output_path: Path to output file
            conversion_options: Additional conversion options

        Returns:
            Command as list of strings
        """
        cmd = ["ebook-convert", str(input_path), str(output_path)]

        # Enhanced KFX-specific options (from legacy converter analysis)
        kfx_options = {
            "output-profile": "kindle_fire",
            "no-inline-toc": True,
            "margin-left": "5",
            "margin-right": "5",
            "margin-top": "5",
            "margin-bottom": "5",
            "change-justification": "left",
            "remove-paragraph-spacing": True,
            "remove-paragraph-spacing-indent-size": "1.5",
            "insert-blank-line": True,
            "insert-blank-line-size": "0.5",
        }

        # Advanced KFX options if plugin supports them
        if self._check_advanced_kfx_plugin():
            kfx_options.update(
                {
                    "enable-heuristics": True,
                    "markup-chapter-headings": True,
                    "remove-fake-margins": True,
                }
            )

        # Override with user-provided options
        if conversion_options:
            kfx_options.update(conversion_options)

        # Add options to command
        for key, value in kfx_options.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])

        return cmd

    def parallel_batch_convert(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        input_formats: Optional[List[str]] = None,
        dry_run: bool = False,
        progress_callback=None,
    ) -> List[ConversionResult]:
        """
        Parallel batch conversion of directory to KFX format.

        This method provides directory-based batch conversion similar to
        the legacy ParallelKFXConverter but with CLI integration.

        Args:
            input_dir: Directory containing books to convert
            output_dir: Output directory (auto-generated if None)
            input_formats: List of input formats to include
            dry_run: If True, only show what would be converted
            progress_callback: Progress callback function

        Returns:
            List of ConversionResult objects
        """
        if not input_dir.exists() or not input_dir.is_dir():
            self.logger.error(
                f"Input directory not found or not a directory: {input_dir}"
            )
            return []

        # Use default formats if not specified
        if not input_formats:
            input_formats = [".epub", ".mobi", ".azw", ".azw3", ".pdf"]

        # Set output directory
        if output_dir is None:
            output_dir = input_dir / "kfx_output"

        output_dir.mkdir(parents=True, exist_ok=True)

        # Find conversion candidates using FormatConverter's finder
        candidates = self._format_converter.find_convertible_files(
            input_dir=input_dir,
            recursive=True,
            progress_callback=progress_callback,
        )

        # Filter by requested formats
        format_extensions = {fmt.lower().lstrip(".") for fmt in input_formats}
        filtered_candidates = [
            f for f in candidates if f.suffix.lower().lstrip(".") in format_extensions
        ]

        if not filtered_candidates:
            self.logger.warning(f"No convertible files found in {input_dir}")
            return []

        self.logger.info(
            f"Found {len(filtered_candidates)} files for KFX batch conversion "
            f"(workers: {self.max_workers})"
        )

        if dry_run:
            self.logger.info("DRY RUN: KFX batch conversion preview")
            results = []
            for i, candidate in enumerate(filtered_candidates):
                output_filename = f"{candidate.stem}_kfx.azw3"
                output_path = output_dir / output_filename

                result = ConversionResult(
                    input_file=candidate,
                    output_file=output_path,
                    input_format=self._format_converter._detect_format(candidate)
                    or BookFormat.EPUB,
                    output_format=BookFormat.KFX,
                    success=True,
                    conversion_time=0.0,
                    file_size_before=candidate.stat().st_size,
                    file_size_after=candidate.stat().st_size,  # Estimate
                )
                results.append(result)

                if progress_callback:
                    progress_callback(
                        (i + 1) / len(filtered_candidates),
                        f"KFX Preview {i + 1}/{len(filtered_candidates)}",
                    )

                self.logger.info(f"Would convert: {candidate.name} → {output_filename}")

            return results

        # Parallel conversion using ThreadPoolExecutor
        conversion_jobs = []
        for candidate in filtered_candidates:
            output_filename = f"{candidate.stem}_kfx.azw3"
            output_path = output_dir / output_filename

            # Skip if already exists
            if not output_path.exists():
                conversion_jobs.append(
                    {
                        "input_path": candidate,
                        "output_path": output_path,
                    }
                )

        if not conversion_jobs:
            self.logger.info("All files already converted to KFX")
            return []

        self.logger.info(f"Processing {len(conversion_jobs)} KFX conversion jobs...")

        results = []
        completed = 0

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(
                    self.convert_single_to_kfx, job["input_path"], job["output_path"]
                ): job
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
                        status_msg = f"KFX {completed}/{len(conversion_jobs)}"
                        if result.success:
                            status_msg += f" - ✓ {result.input_file.name}"
                        else:
                            status_msg += f" - ✗ {result.input_file.name}"
                        progress_callback(progress_percentage, status_msg)

                except Exception as exc:
                    # Handle unexpected exceptions
                    error_result = ConversionResult(
                        input_file=job["input_path"],
                        output_file=job["output_path"],
                        input_format=self._format_converter._detect_format(
                            job["input_path"]
                        )
                        or BookFormat.EPUB,
                        output_format=BookFormat.KFX,
                        success=False,
                        error=f"Unexpected KFX conversion error: {str(exc)}",
                    )
                    results.append(error_result)
                    completed += 1

                    self.logger.error(
                        f"✗ KFX job for {job['input_path'].name} generated exception: {exc}"
                    )

        # Summary
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        total_size = sum(r.file_size_after or 0 for r in successful) / 1024 / 1024

        self.logger.info("KFX batch conversion summary:")
        self.logger.info(f"  ✓ Successful: {len(successful)}")
        self.logger.info(f"  ✗ Failed: {len(failed)}")
        self.logger.info(f"  📊 Total KFX output: {total_size:.1f} MB")

        if failed:
            self.logger.warning("Failed KFX conversions:")
            for fail in failed[:3]:  # Show first 3
                self.logger.warning(f"  ✗ {fail.input_file.name}: {fail.error}")
            if len(failed) > 3:
                self.logger.warning(f"  ... and {len(failed) - 3} more KFX failures")

        return results

    def convert_library_to_kfx(
        self,
        book_filter: Optional[str] = None,
        limit: Optional[int] = None,
        dry_run: bool = False,
        progress_callback=None,
    ) -> List[ConversionResult]:
        """
        Convert books from Calibre library to KFX format.

        This method provides library-based conversion similar to the legacy
        ParallelKFXConverter but with enhanced CLI integration.

        Args:
            book_filter: Search filter for selecting books
            limit: Maximum number of books to convert
            dry_run: If True, only show what would be converted
            progress_callback: Progress callback function

        Returns:
            List of ConversionResult objects
        """
        if not self.library_path:
            error_msg = "No Calibre library path configured"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        if not self._check_library_access():
            error_msg = f"Calibre library not accessible: {self.library_path}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            # Build calibredb command
            cmd = ["calibredb", "--library-path", str(self.library_path)]
            cmd.extend(["list", "--fields", "id,title,authors,formats,path"])

            if book_filter:
                cmd.extend(["-s", book_filter])
            if limit:
                cmd.extend(["--limit", str(limit)])

            self.logger.info(f"Querying Calibre library: {self.library_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                error_msg = f"Failed to query Calibre library: {result.stderr}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)

            # Parse library books
            books = []
            lines = result.stdout.strip().split("\n")[1:]  # Skip header

            for line in lines:
                if line.strip():
                    parts = line.split("\t")
                    if len(parts) >= 5:
                        book_id, title, authors, formats, path = parts[:5]

                        # Check if KFX conversion is needed
                        if "KFX" not in formats.upper():
                            book_path = self.library_path / path
                            if book_path.exists():
                                books.append(
                                    {
                                        "id": book_id,
                                        "title": title,
                                        "authors": authors,
                                        "formats": formats,
                                        "path": book_path,
                                    }
                                )

            if not books:
                self.logger.info("No books found needing KFX conversion")
                return []

            self.logger.info(f"Found {len(books)} library books for KFX conversion")

            if dry_run:
                self.logger.info("DRY RUN: Library KFX conversion preview")
                for book in books:
                    self.logger.info(
                        f"Would convert: {book['title']} by {book['authors']}"
                    )
                return []

            # Convert each book directory
            all_results = []
            for i, book in enumerate(books):
                self.logger.info(
                    f"Converting library book ({i + 1}/{len(books)}): {book['title']}"
                )

                try:
                    # Convert all files in the book's directory
                    book_results = self.parallel_batch_convert(
                        input_dir=book["path"],
                        dry_run=False,
                        progress_callback=progress_callback,
                    )
                    all_results.extend(book_results)

                except Exception as e:
                    self.logger.error(
                        f"Failed to convert library book {book['title']}: {e}"
                    )
                    # Continue with next book

            return all_results

        except subprocess.TimeoutExpired:
            error_msg = "Timeout querying Calibre library"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Library KFX conversion error: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

    def install_kfx_plugin_guidance(self):
        """
        Provide guidance for KFX Output plugin installation.

        This method provides helpful information for users to install
        the required KFX Output plugin.
        """
        self.logger.info("=== KFX Output Plugin Installation Guide ===")
        self.logger.info("The KFX Output plugin is required for KFX conversion.")
        self.logger.info("")
        self.logger.info("Installation steps:")
        self.logger.info("1. Download KFX Output plugin:")
        self.logger.info("   https://www.mobileread.com/forums/showthread.php?t=272407")
        self.logger.info("")
        self.logger.info("2. Install via command line:")
        self.logger.info("   calibre-customize -a KFXOutput.zip")
        self.logger.info("")
        self.logger.info("3. Or install via Calibre GUI:")
        self.logger.info("   Calibre → Preferences → Plugins → Load plugin from file")
        self.logger.info("")
        self.logger.info("4. Restart Calibre after installation")
        self.logger.info("")

        # Check current plugin status
        if self._check_advanced_kfx_plugin():
            self.logger.info("✓ KFX Output plugin is currently available")
        else:
            self.logger.warning("⚠ KFX Output plugin not detected")

        return self._check_advanced_kfx_plugin()
