"""
KFX conversion module for Calibre Books CLI.

This module provides functionality for converting eBook files to KFX format
for Goodreads integration, using the existing parallel converter logic.
"""

import logging
import subprocess
import os
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, TYPE_CHECKING

from ..utils.logging import LoggerMixin
from .book import Book, ConversionResult

if TYPE_CHECKING:
    from ..config.manager import ConfigManager


class KFXConverter(LoggerMixin):
    """
    KFX conversion service with parallel processing support.
    
    Integrates the existing parallel_kfx_converter.py logic into the CLI tool.
    """
    
    def __init__(self, config_manager: 'ConfigManager'):
        """
        Initialize KFX converter.
        
        Args:
            config_manager: Configuration manager instance
        """
        super().__init__()
        self.config_manager = config_manager
        
        # Get conversion-specific configuration with error handling
        try:
            conversion_config = config_manager.get_conversion_config()
            self.max_workers = conversion_config.get('max_workers', 4)
            self.logger.debug(f"Initialized KFX converter with max_workers: {self.max_workers}")
        except Exception as e:
            self.logger.warning(f"Failed to load conversion config, using defaults: {e}")
            self.max_workers = 4
        
        # Store other config sections for use by converter methods
        try:
            self.calibre_config = config_manager.get_calibre_config()
        except Exception as e:
            self.logger.warning(f"Failed to load Calibre config, using defaults: {e}")
            self.calibre_config = {}
        
        # Import existing parallel KFX converter
        try:
            import sys
            parent_dir = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(parent_dir))
            
            from parallel_kfx_converter import ParallelKFXConverter
            self._converter = ParallelKFXConverter(max_workers=self.max_workers)
            self.logger.info("Parallel KFX converter initialized")
        except ImportError as e:
            self.logger.warning(f"Parallel KFX converter not available: {e}")
            self._converter = None
    
    def check_system_requirements(self) -> Dict[str, bool]:
        """Check if system requirements for KFX conversion are met."""
        requirements = {
            'calibre': self._check_calibre(),
            'ebook-convert': self._check_ebook_convert(),
            'kfx_plugin': self._check_kfx_plugin(),
            'kindle_previewer': self._check_kindle_previewer(),
        }
        
        self.logger.info(f"System requirements check: {requirements}")
        return requirements
    
    def _check_calibre(self) -> bool:
        """Check if Calibre is installed."""
        try:
            result = subprocess.run(['calibre', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _check_ebook_convert(self) -> bool:
        """Check if ebook-convert is available."""
        try:
            result = subprocess.run(['ebook-convert', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _check_kfx_plugin(self) -> bool:
        """Check if KFX Output Plugin is installed."""
        if self._converter:
            return self._converter.check_kfx_plugin()
        return False
    
    def _check_kindle_previewer(self) -> bool:
        """Check if Kindle Previewer 3 is installed."""
        if self._converter:
            return self._converter.check_kindle_previewer()
        return False
    
    def convert_books_to_kfx(
        self,
        books: List[Book],
        output_dir: Optional[Path] = None,
        parallel: int = 4,
        conversion_options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> List[ConversionResult]:
        """
        Convert multiple books to KFX format in parallel.
        
        Args:
            books: List of books to convert
            output_dir: Output directory for KFX files
            parallel: Number of parallel workers
            conversion_options: Custom conversion options
            progress_callback: Progress callback function
            
        Returns:
            List of conversion results
        """
        self.logger.info(f"Converting {len(books)} books to KFX format")
        
        if not self._converter:
            raise RuntimeError("KFX converter not available")
        
        results = []
        
        # Set up output directory
        if not output_dir:
            output_dir = Path("./kfx_output")
        output_dir.mkdir(exist_ok=True)
        
        # Create conversion jobs
        conversion_jobs = []
        for book in books:
            if not book.file_path or not book.file_path.exists():
                results.append(ConversionResult(
                    book=book,
                    success=False,
                    error="Source file not found"
                ))
                continue
            
            output_filename = f"{book.file_path.stem}_kfx.azw3"
            output_path = output_dir / output_filename
            
            conversion_jobs.append({
                'book': book,
                'input_path': book.file_path,
                'output_path': output_path
            })
        
        if not conversion_jobs:
            return results
        
        # Parallel conversion
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            future_to_job = {
                executor.submit(
                    self._convert_single_book,
                    job['book'],
                    job['input_path'],
                    job['output_path'],
                    conversion_options
                ): job for job in conversion_jobs
            }
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_job):
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(conversion_jobs))
                
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    job = future_to_job[future]
                    self.logger.error(f"Conversion failed for {job['book'].metadata.title}: {exc}")
                    results.append(ConversionResult(
                        book=job['book'],
                        success=False,
                        error=str(exc)
                    ))
        
        successful = sum(1 for r in results if r.success)
        self.logger.info(f"KFX conversion completed: {successful}/{len(results)} successful")
        
        return results
    
    def _convert_single_book(
        self,
        book: Book,
        input_path: Path,
        output_path: Path,
        conversion_options: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """Convert a single book to KFX format."""
        try:
            self.logger.debug(f"Converting {book.metadata.title} to KFX")
            
            # Use existing converter logic
            if self._converter:
                result = self._converter.convert_single_to_kfx(
                    str(input_path),
                    str(output_path),
                    conversion_options
                )
                
                return ConversionResult(
                    book=book,
                    success=result['success'],
                    output_path=Path(result['output_path']) if result['success'] else None,
                    error=result.get('error'),
                    output_format='KFX',
                    file_size=result.get('file_size', 0)
                )
            else:
                # Fallback to basic ebook-convert
                return self._fallback_convert(book, input_path, output_path)
                
        except Exception as e:
            self.logger.error(f"Failed to convert {book.metadata.title}: {e}")
            return ConversionResult(
                book=book,
                success=False,
                error=str(e)
            )
    
    def _fallback_convert(self, book: Book, input_path: Path, output_path: Path) -> ConversionResult:
        """Fallback conversion using basic ebook-convert."""
        try:
            cmd = [
                'ebook-convert',
                str(input_path),
                str(output_path),
                '--output-profile', 'kindle_fire',
                '--no-inline-toc',
                '--margin-left', '5',
                '--margin-right', '5',
                '--margin-top', '5', 
                '--margin-bottom', '5'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                file_size = output_path.stat().st_size if output_path.exists() else 0
                return ConversionResult(
                    book=book,
                    success=True,
                    output_path=output_path,
                    output_format='AZW3',
                    file_size=file_size
                )
            else:
                return ConversionResult(
                    book=book,
                    success=False,
                    error=f"ebook-convert failed: {result.stderr}"
                )
                
        except subprocess.TimeoutExpired:
            return ConversionResult(
                book=book,
                success=False,
                error="Conversion timed out (300s)"
            )
        except Exception as e:
            return ConversionResult(
                book=book,
                success=False,
                error=str(e)
            )