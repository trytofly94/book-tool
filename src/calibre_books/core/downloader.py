"""
Book downloader and KFX conversion module for Calibre Books CLI.

This module provides functionality for downloading books and converting eBook 
files to KFX format for Goodreads integration.
"""

import subprocess
import concurrent.futures
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, TYPE_CHECKING
from dataclasses import dataclass

from ..utils.logging import LoggerMixin
from .book import Book, ConversionResult, BookFormat

if TYPE_CHECKING:
    from ..config.manager import ConfigManager


@dataclass
class BookInfo:
    """Information about a book to download."""
    title: str
    author: str
    format: str = "mobi"


@dataclass
class DownloadResult:
    """Result of a book download operation."""
    book: BookInfo
    filepath: Optional[Path]
    success: bool
    error: Optional[str] = None


class BookDownloader(LoggerMixin):
    """
    Book download service for various sources.
    
    Currently supports librarian CLI integration for book downloads.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize book downloader.
        
        Args:
            config: Download configuration dictionary
        """
        super().__init__()
        self.config = config
        self.download_path = Path(config.get('download_path', './downloads'))
        self.preferred_format = config.get('preferred_format', 'mobi')
        
        # Ensure download directory exists
        self.download_path.mkdir(exist_ok=True, parents=True)
        
        self.logger.debug(f"BookDownloader initialized with path: {self.download_path}")

    def download_books(
        self,
        series: Optional[str] = None,
        author: Optional[str] = None,
        title: Optional[str] = None,
        format: str = "mobi",
        output_dir: Optional[Path] = None,
        max_results: int = 10,
        quality: str = "high",
        progress_callback: Optional[Callable] = None,
    ) -> List[DownloadResult]:
        """
        Download books based on search criteria.
        
        Args:
            series: Series name to search for
            author: Author name to search for
            title: Book title to search for
            format: Preferred format (mobi, epub, pdf, azw3)
            output_dir: Output directory for downloads
            max_results: Maximum number of results to download
            quality: Quality preference (high, medium, low)
            progress_callback: Progress callback function
            
        Returns:
            List of download results
        """
        self.logger.info("Starting book download with search criteria")
        
        # For now, return empty results with a helpful message
        # This is a stub implementation that prevents CLI crashes
        results = []
        
        # Create a placeholder result indicating functionality is not yet implemented
        placeholder_book = BookInfo(
            title=title or f"Books by {author}" if author else f"Series: {series}",
            author=author or "Unknown Author",
            format=format
        )
        
        results.append(DownloadResult(
            book=placeholder_book,
            filepath=None,
            success=False,
            error="BookDownloader functionality is not yet fully implemented. Please use legacy scripts for now."
        ))
        
        return results

    def download_batch(
        self,
        books: List[BookInfo],
        format: str = "mobi",
        output_dir: Optional[Path] = None,
        parallel: int = 1,
        progress_callback: Optional[Callable] = None,
    ) -> List[DownloadResult]:
        """
        Download multiple books from a list.
        
        Args:
            books: List of books to download
            format: Preferred format
            output_dir: Output directory
            parallel: Number of parallel downloads
            progress_callback: Progress callback function
            
        Returns:
            List of download results
        """
        self.logger.info(f"Starting batch download of {len(books)} books")
        
        results = []
        for book in books:
            results.append(DownloadResult(
                book=book,
                filepath=None,
                success=False,
                error="BookDownloader batch functionality is not yet fully implemented."
            ))
        
        return results

    def download_from_url(
        self,
        url: str,
        output_dir: Optional[Path] = None,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> DownloadResult:
        """
        Download book from direct URL.
        
        Args:
            url: Direct URL to download from
            output_dir: Output directory
            filename: Custom filename
            progress_callback: Progress callback function
            
        Returns:
            Download result
        """
        self.logger.info(f"Starting URL download from: {url}")
        
        placeholder_book = BookInfo(
            title=filename or "URL Download",
            author="Unknown",
            format="unknown"
        )
        
        return DownloadResult(
            book=placeholder_book,
            filepath=None,
            success=False,
            error="URL download functionality is not yet fully implemented."
        )

    def parse_book_list(self, file_path: Path) -> List[BookInfo]:
        """
        Parse book list from file.
        
        Args:
            file_path: Path to file containing book list
            
        Returns:
            List of BookInfo objects
        """
        books = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('|')
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        author = parts[1].strip()
                    else:
                        title = parts[0].strip()
                        author = "Unknown Author"
                    
                    books.append(BookInfo(title=title, author=author))
                        
        except Exception as e:
            self.logger.error(f"Failed to parse book list from {file_path}: {e}")
            
        return books


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
            # Use max_parallel from config schema (not max_workers)
            self.max_workers = conversion_config.get('max_parallel', 4)
            msg = (
                f"Initialized KFX converter with "
                f"max_workers: {self.max_workers}"
            )
            self.logger.debug(msg)
        except Exception as e:
            msg = f"Failed to load conversion config, using defaults: {e}"
            self.logger.warning(msg)
            self.max_workers = 4

        # Store other config sections for use by converter methods
        try:
            self.calibre_config = config_manager.get_calibre_config()
        except Exception as e:
            msg = f"Failed to load Calibre config, using defaults: {e}"
            self.logger.warning(msg)
            self.calibre_config = {}

        # Import existing parallel KFX converter
        try:
            import sys
            parent_dir = Path(__file__).parent.parent.parent
            sys.path.insert(0, str(parent_dir))

            from parallel_kfx_converter import ParallelKFXConverter
            self._converter = ParallelKFXConverter(
                max_workers=self.max_workers
            )
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
            result = subprocess.run(
                ['calibre', '--version'],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_ebook_convert(self) -> bool:
        """Check if ebook-convert is available."""
        try:
            result = subprocess.run(
                ['ebook-convert', '--version'],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_kfx_plugin(self) -> bool:
        """Check if KFX Output Plugin is installed."""
        # Use FormatConverter's plugin validation since it has the actual implementation
        try:
            from .converter import FormatConverter
            temp_converter = FormatConverter(self.config_manager)
            return temp_converter.validate_kfx_plugin()
        except Exception as e:
            self.logger.error(f"Failed to validate KFX plugin: {e}")
            return False

    def validate_kfx_plugin(self) -> bool:
        """Validate KFX plugin - delegate to FormatConverter for consistency."""
        return self._check_kfx_plugin()

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
                    input_file=book.file_path or Path("unknown"),
                    output_file=None,
                    input_format=book.metadata.format or BookFormat.EPUB,
                    output_format=BookFormat.KFX,
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
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=parallel
        ) as executor:
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
            for future in concurrent.futures.as_completed(
                future_to_job
            ):
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(conversion_jobs))

                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    job = future_to_job[future]
                    title = job['book'].metadata.title
                    self.logger.error(f"Conversion failed for {title}: {exc}")
                    results.append(ConversionResult(
                        input_file=job['input_path'],
                        output_file=None,
                        input_format=(
                            job['book'].metadata.format or BookFormat.EPUB
                        ),
                        output_format=BookFormat.KFX,
                        success=False,
                        error=str(exc)
                    ))

        successful = sum(1 for r in results if r.success)
        msg = (
            f"KFX conversion completed: {successful}/{len(results)} successful"
        )
        self.logger.info(msg)

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
                    input_file=input_path,
                    output_file=(
                        Path(result['output_path'])
                        if result['success'] else None
                    ),
                    input_format=book.metadata.format or BookFormat.EPUB,
                    output_format=BookFormat.KFX,
                    success=result['success'],
                    error=result.get('error'),
                    file_size_after=result.get('file_size', 0)
                )
            else:
                # Fallback to basic ebook-convert
                return self._fallback_convert(book, input_path, output_path)

        except Exception as e:
            self.logger.error(f"Failed to convert {book.metadata.title}: {e}")
            return ConversionResult(
                input_file=input_path,
                output_file=None,
                input_format=book.metadata.format or BookFormat.EPUB,
                output_format=BookFormat.KFX,
                success=False,
                error=str(e)
            )

    def _fallback_convert(
        self,
        book: Book,
        input_path: Path,
        output_path: Path
    ) -> ConversionResult:
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

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )

            if result.returncode == 0:
                file_size = (
                    output_path.stat().st_size if output_path.exists() else 0
                )
                return ConversionResult(
                    input_file=input_path,
                    output_file=output_path,
                    input_format=book.metadata.format or BookFormat.EPUB,
                    output_format=BookFormat.AZW3,
                    success=True,
                    file_size_after=file_size
                )
            else:
                return ConversionResult(
                    input_file=input_path,
                    output_file=None,
                    input_format=book.metadata.format or BookFormat.EPUB,
                    output_format=BookFormat.AZW3,
                    success=False,
                    error=f"ebook-convert failed: {result.stderr}"
                )

        except subprocess.TimeoutExpired:
            return ConversionResult(
                input_file=input_path,
                output_file=None,
                input_format=book.metadata.format or BookFormat.EPUB,
                output_format=BookFormat.AZW3,
                success=False,
                error="Conversion timed out (300s)"
            )
        except Exception as e:
            return ConversionResult(
                input_file=input_path,
                output_file=None,
                input_format=book.metadata.format or BookFormat.EPUB,
                output_format=BookFormat.AZW3,
                success=False,
                error=str(e)
            )
