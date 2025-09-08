"""
Book download module for Calibre Books CLI.

This module provides functionality for downloading books from various sources
using the librarian CLI tool and other download services.
"""

import subprocess
import concurrent.futures
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass

from ..utils.logging import LoggerMixin
from .exceptions import (
    DownloadError,
    LibrarianError,
    ValidationError,
    NetworkError,
    FormatError,
    ConfigurationError,
)


@dataclass
class DownloadResult:
    """Result of a book download operation."""

    title: str
    author: str
    filepath: Optional[Path]
    success: bool
    error: Optional[str] = None
    format: Optional[str] = None
    file_size: Optional[int] = None


@dataclass
class BookRequest:
    """A book download request."""

    title: str
    author: Optional[str] = None
    series: Optional[str] = None
    format: str = "mobi"


class BookDownloader(LoggerMixin):
    """
    Book download service with support for multiple sources.

    Integrates with librarian CLI tool for downloading books from various
    sources with support for parallel processing and progress tracking.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize book downloader.

        Args:
            config: Download configuration dictionary
        """
        super().__init__()
        self.config = config

        # Set up configuration with defaults
        self.default_format = config.get("default_format", "mobi")
        self.download_path = Path(
            config.get("download_path", "~/Downloads/Books")
        ).expanduser()
        self.librarian_path = config.get("librarian_path", "librarian")
        self.max_parallel = config.get("max_parallel", 1)
        self.quality = config.get("quality", "high")

        # Validate configuration
        self._validate_configuration()

        # Ensure download directory exists
        self.download_path.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            f"Initialized BookDownloader with download_path: {self.download_path}"
        )

    def check_system_requirements(self) -> Dict[str, bool]:
        """Check if system requirements for downloading are met."""
        requirements = {
            "librarian": self._check_librarian(),
        }

        self.logger.info(f"System requirements check: {requirements}")
        return requirements

    def _validate_configuration(self):
        """Validate download configuration."""
        # Validate librarian path
        self._validate_librarian_path()

        # Validate download path
        if not self.download_path.parent.exists():
            raise ConfigurationError(
                f"Parent directory of download path does not exist: {self.download_path.parent}",
                config_key="download_path",
                config_value=str(self.download_path),
            )

        # Validate max_parallel setting
        if not isinstance(self.max_parallel, int) or self.max_parallel < 1:
            raise ConfigurationError(
                f"max_parallel must be a positive integer, got: {self.max_parallel}",
                config_key="max_parallel",
                config_value=str(self.max_parallel),
            )

        # Validate quality setting
        valid_qualities = {"low", "medium", "high"}
        if self.quality not in valid_qualities:
            raise ConfigurationError(
                f"quality must be one of {valid_qualities}, got: {self.quality}",
                config_key="quality",
                config_value=self.quality,
            )

    def _validate_librarian_path(self):
        """Validate that librarian CLI is available and executable."""
        # Check if path is absolute and executable
        librarian_path = Path(self.librarian_path)

        if librarian_path.is_absolute():
            # Absolute path - check existence and executability directly
            if not librarian_path.exists():
                raise ConfigurationError(
                    f"Librarian executable not found at: {self.librarian_path}",
                    config_key="librarian_path",
                    config_value=self.librarian_path,
                )
            if not os.access(librarian_path, os.X_OK):
                raise ConfigurationError(
                    f"Librarian executable is not executable: {self.librarian_path}",
                    config_key="librarian_path",
                    config_value=self.librarian_path,
                )
        else:
            # Relative path or command name - check if it's in PATH
            try:
                result = subprocess.run(
                    [self.librarian_path, "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    raise ConfigurationError(
                        f"Librarian CLI test failed with return code {result.returncode}",
                        config_key="librarian_path",
                        config_value=self.librarian_path,
                    )
            except FileNotFoundError:
                raise ConfigurationError(
                    f"Librarian executable not found in PATH: {self.librarian_path}",
                    config_key="librarian_path",
                    config_value=self.librarian_path,
                )
            except subprocess.TimeoutExpired:
                raise ConfigurationError(
                    f"Librarian CLI test timed out for: {self.librarian_path}",
                    config_key="librarian_path",
                    config_value=self.librarian_path,
                )

    def _check_librarian(self) -> bool:
        """Check if librarian CLI is available."""
        try:
            self._validate_librarian_path()
            return True
        except ConfigurationError:
            return False

    def download_books(
        self,
        series: Optional[str] = None,
        author: Optional[str] = None,
        title: Optional[str] = None,
        format: str = "mobi",
        output_dir: Optional[Path] = None,
        max_results: int = 10,
        quality: str = "high",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[DownloadResult]:
        """
        Download books based on search criteria.

        Args:
            series: Series name to search for
            author: Author name to search for
            title: Book title to search for
            format: Preferred download format
            output_dir: Output directory (overrides default)
            max_results: Maximum number of books to download
            quality: Download quality preference
            progress_callback: Progress callback function

        Returns:
            List of download results
        """
        if not any([series, author, title]):
            raise ValueError("Must specify at least one of: series, author, or title")

        self.logger.info(
            f"Downloading books: series={series}, author={author}, title={title}"
        )

        # Use provided output directory or default
        target_dir = Path(output_dir).expanduser() if output_dir else self.download_path
        target_dir.mkdir(parents=True, exist_ok=True)

        # Build search query
        search_terms = []
        if author:
            search_terms.append(author)
        if series:
            search_terms.append(series)
        if title:
            search_terms.append(title)
        search_terms.append(format)

        search_query = " ".join(search_terms)

        try:
            # Search for books
            search_results = self._search_books(search_query, target_dir)

            if not search_results:
                self.logger.warning(f"No books found for query: {search_query}")
                return []

            # Limit results
            books_to_download = search_results[:max_results]

            # Filter by format
            filtered_books = [
                book
                for book in books_to_download
                if book.get("format", "").lower() == format.lower()
            ]

            self.logger.info(
                f"Found {len(filtered_books)} books matching format {format}"
            )

            if not filtered_books:
                self.logger.warning(f"No books found in {format} format")
                return []

            # Download books
            results = []
            total_books = len(filtered_books)

            for i, book_data in enumerate(filtered_books):
                if progress_callback:
                    progress_callback(i, total_books)

                result = self._download_single_book(book_data, target_dir, format)
                results.append(result)

                if not result.success:
                    self.logger.error(f"Failed to download: {result.title}")
                else:
                    self.logger.info(f"Downloaded: {result.title}")

            if progress_callback:
                progress_callback(total_books, total_books)

            successful = sum(1 for r in results if r.success)
            self.logger.info(
                f"Download completed: {successful}/{len(results)} successful"
            )

            return results

        except (LibrarianError, NetworkError) as e:
            self.logger.error(f"Download failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected download error: {e}")
            raise DownloadError(f"Download failed: {e}")

    def download_batch(
        self,
        books: List[BookRequest],
        format: str = "mobi",
        output_dir: Optional[Path] = None,
        parallel: int = 1,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[DownloadResult]:
        """
        Download multiple books in parallel.

        Args:
            books: List of book requests to download
            format: Preferred download format
            output_dir: Output directory (overrides default)
            parallel: Number of parallel downloads
            progress_callback: Progress callback function

        Returns:
            List of download results
        """
        if not books:
            return []

        self.logger.info(f"Starting batch download of {len(books)} books")

        # Use provided output directory or default
        target_dir = Path(output_dir).expanduser() if output_dir else self.download_path
        target_dir.mkdir(parents=True, exist_ok=True)

        results = []

        if parallel <= 1:
            # Sequential download
            for i, book in enumerate(books):
                if progress_callback:
                    progress_callback(i, len(books))

                result = self._download_book_request(book, target_dir, format)
                results.append(result)
        else:
            # Parallel download with improved resource management
            results = self._download_parallel_with_timeout(
                books, target_dir, format, parallel, progress_callback
            )

        successful = sum(1 for r in results if r.success)
        self.logger.info(
            f"Batch download completed: {successful}/{len(results)} successful"
        )

        return results

    def download_from_url(
        self,
        url: str,
        output_dir: Optional[Path] = None,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DownloadResult:
        """
        Download book from direct URL.

        Args:
            url: Direct URL to download from
            output_dir: Output directory (overrides default)
            filename: Custom filename for the download
            progress_callback: Progress callback function

        Returns:
            Download result
        """
        self.logger.info(f"Downloading from URL: {url}")

        # Use provided output directory or default
        target_dir = Path(output_dir).expanduser() if output_dir else self.download_path
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            if progress_callback:
                progress_callback(0, 1)

            # Extract filename from URL if not provided
            if not filename:
                filename = Path(url).name
                if not filename or "." not in filename:
                    filename = "downloaded_book.epub"  # Default fallback

            output_path = target_dir / filename

            # Use wget or curl for direct download
            try:
                # Try wget first
                result = subprocess.run(
                    ["wget", url, "-O", str(output_path)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode != 0:
                    # Fallback to curl
                    result = subprocess.run(
                        ["curl", "-L", url, "-o", str(output_path)],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )

                if result.returncode != 0:
                    raise NetworkError(f"Download failed: {result.stderr}", url=url)

            except subprocess.TimeoutExpired:
                raise NetworkError("Download timed out", url=url, timeout=300)

            # Check if file was downloaded
            if output_path.exists() and output_path.stat().st_size > 0:
                file_size = output_path.stat().st_size

                if progress_callback:
                    progress_callback(1, 1)

                self.logger.info(f"Successfully downloaded: {filename}")

                return DownloadResult(
                    title=filename,
                    author="Unknown",
                    filepath=output_path,
                    success=True,
                    file_size=file_size,
                )
            else:
                return DownloadResult(
                    title=filename,
                    author="Unknown",
                    filepath=None,
                    success=False,
                    error="Downloaded file is empty or missing",
                )

        except subprocess.TimeoutExpired:
            self.logger.error(f"URL download timed out: {url}")
            return DownloadResult(
                title=filename or "Unknown",
                author="Unknown",
                filepath=None,
                success=False,
                error="Download timed out",
            )
        except NetworkError as e:
            self.logger.error(f"Network error downloading {url}: {e}")
            return DownloadResult(
                title=filename or "Unknown",
                author="Unknown",
                filepath=None,
                success=False,
                error=str(e),
            )
        except Exception as e:
            self.logger.error(f"URL download failed: {e}")
            return DownloadResult(
                title=filename or "Unknown",
                author="Unknown",
                filepath=None,
                success=False,
                error=str(e),
            )

    def parse_book_list(self, file_path) -> List[BookRequest]:
        """
        Parse book list from file.

        Supported file formats: .txt, .csv
        File format: One book per line, either:
        - "Title"
        - "Title|Author"
        - "Title|Author|Series"

        Lines starting with # are treated as comments and ignored.
        Empty lines are ignored.

        Args:
            file_path: Path to file containing book list (string or Path object)

        Returns:
            List of book requests

        Raises:
            ValidationError: If file doesn't exist or has invalid extension
            FormatError: If file content is malformed or unreadable
        """
        # Convert to Path object if string
        file_path = Path(file_path)

        # Validate file existence
        if not file_path.exists():
            raise ValidationError(
                f"Book list file not found: {file_path}",
                field="file_path",
                value=str(file_path),
            )

        # Validate file extension
        allowed_extensions = {".txt", ".csv"}
        if file_path.suffix.lower() not in allowed_extensions:
            raise ValidationError(
                f"Unsupported file format: {file_path.suffix}. Supported formats: {', '.join(allowed_extensions)}",
                field="file_extension",
                value=file_path.suffix,
            )

        # Check if file is readable
        if not os.access(file_path, os.R_OK):
            raise ValidationError(
                f"File is not readable: {file_path}",
                field="file_permissions",
                value=str(file_path),
            )

        books = []
        invalid_lines = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue  # Skip empty lines and comments

                    # Validate line format
                    if "|" in line:
                        parts = line.split("|")
                        # Check for empty parts
                        if any(not part.strip() for part in parts):
                            invalid_lines.append(
                                f"Line {line_num}: Empty field in '{line}'"
                            )
                            continue
                    else:
                        # Single title - ensure it's not empty after stripping
                        if not line.strip():
                            continue

                    parts = line.split("|")

                    try:
                        if len(parts) == 1:
                            # Just title
                            title = parts[0].strip()
                            if not title:
                                invalid_lines.append(
                                    f"Line {line_num}: Empty title in '{line}'"
                                )
                                continue
                            books.append(BookRequest(title=title))
                        elif len(parts) == 2:
                            # Title and author
                            title = parts[0].strip()
                            author = parts[1].strip()
                            if not title:
                                invalid_lines.append(
                                    f"Line {line_num}: Empty title in '{line}'"
                                )
                                continue
                            books.append(
                                BookRequest(
                                    title=title, author=author if author else None
                                )
                            )
                        elif len(parts) >= 3:
                            # Title, author, and series
                            title = parts[0].strip()
                            author = parts[1].strip()
                            series = parts[2].strip()
                            if not title:
                                invalid_lines.append(
                                    f"Line {line_num}: Empty title in '{line}'"
                                )
                                continue
                            books.append(
                                BookRequest(
                                    title=title,
                                    author=author if author else None,
                                    series=series if series else None,
                                )
                            )
                        else:
                            invalid_lines.append(
                                f"Line {line_num}: Invalid format '{line}'"
                            )
                    except Exception as e:
                        invalid_lines.append(
                            f"Line {line_num}: Error processing '{line}': {e}"
                        )

        except UnicodeDecodeError as e:
            self.logger.error(f"File encoding error in {file_path}: {e}")
            raise FormatError(
                f"Unable to read file {file_path}: invalid encoding",
                filename=str(file_path),
            )
        except PermissionError as e:
            self.logger.error(f"Permission denied reading {file_path}: {e}")
            raise ValidationError(f"Permission denied reading file: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to parse book list: {e}")
            raise FormatError(
                f"Failed to parse book list from {file_path}: {e}",
                filename=str(file_path),
            )

        # Report invalid lines but continue processing
        if invalid_lines:
            self.logger.warning(
                f"Found {len(invalid_lines)} invalid lines in {file_path}:"
            )
            for invalid_line in invalid_lines[:5]:  # Show first 5 invalid lines
                self.logger.warning(f"  {invalid_line}")
            if len(invalid_lines) > 5:
                self.logger.warning(f"  ... and {len(invalid_lines) - 5} more")

        if not books:
            raise FormatError(
                f"No valid book entries found in {file_path}", filename=str(file_path)
            )

        self.logger.info(
            f"Parsed {len(books)} books from {file_path} ({len(invalid_lines)} invalid lines skipped)"
        )
        return books

    def _search_books(
        self, search_query: str, target_dir: Path
    ) -> List[Dict[str, Any]]:
        """Search for books using librarian CLI."""
        try:
            # Run librarian search
            result = subprocess.run(
                [self.librarian_path, "-p", str(target_dir), "search", search_query],
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )

            # Load search results from JSON file
            results_file = target_dir / "search_results.json"
            if not results_file.exists():
                self.logger.warning("Search results file not found")
                return []

            with open(results_file, "r") as f:
                search_results = json.load(f)

            self.logger.info(f"Found {len(search_results)} search results")
            return search_results

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Search failed: {e}")
            return []
        except subprocess.TimeoutExpired:
            self.logger.error("Search timed out")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse search results: {e}")
            return []

    def _download_single_book(
        self, book_data: Dict[str, Any], target_dir: Path, format: str
    ) -> DownloadResult:
        """Download a single book from search results."""
        title = book_data.get("title", "Unknown")
        author = book_data.get("author", "Unknown")
        hash_id = book_data.get("hash", "")

        if not hash_id:
            return DownloadResult(
                title=title,
                author=author,
                filepath=None,
                success=False,
                error="No hash ID found",
            )

        # Create safe filename
        safe_filename = self._create_safe_filename(title, format)

        try:
            # Download using librarian
            result = subprocess.run(
                [self.librarian_path, "download", hash_id, safe_filename],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                return DownloadResult(
                    title=title,
                    author=author,
                    filepath=None,
                    success=False,
                    error=f"Download failed: {result.stderr}",
                )

            # Check if file was downloaded to Downloads folder and move it
            downloads_path = Path.home() / "Downloads" / safe_filename
            target_path = target_dir / safe_filename

            if downloads_path.exists():
                downloads_path.rename(target_path)

            if target_path.exists():
                file_size = target_path.stat().st_size
                return DownloadResult(
                    title=title,
                    author=author,
                    filepath=target_path,
                    success=True,
                    format=format,
                    file_size=file_size,
                )
            else:
                return DownloadResult(
                    title=title,
                    author=author,
                    filepath=None,
                    success=False,
                    error="Downloaded file not found",
                )

        except subprocess.TimeoutExpired:
            return DownloadResult(
                title=title,
                author=author,
                filepath=None,
                success=False,
                error="Download timed out",
            )
        except subprocess.CalledProcessError as e:
            return DownloadResult(
                title=title,
                author=author,
                filepath=None,
                success=False,
                error=f"Librarian command failed: {e.stderr if hasattr(e, 'stderr') else str(e)}",
            )
        except Exception as e:
            return DownloadResult(
                title=title, author=author, filepath=None, success=False, error=str(e)
            )

    def _download_book_request(
        self, book: BookRequest, target_dir: Path, format: str
    ) -> DownloadResult:
        """Download a single book from a book request."""
        # Build search query from book request
        search_terms = []
        if book.author:
            search_terms.append(book.author)
        if book.series:
            search_terms.append(book.series)
        search_terms.append(book.title)
        search_terms.append(format)

        search_query = " ".join(search_terms)

        try:
            # Search for the book
            search_results = self._search_books(search_query, target_dir)

            if not search_results:
                return DownloadResult(
                    title=book.title,
                    author=book.author or "Unknown",
                    filepath=None,
                    success=False,
                    error="No search results found",
                )

            # Find best match (first result with matching format)
            best_match = None
            for result in search_results:
                if result.get("format", "").lower() == format.lower():
                    best_match = result
                    break

            if not best_match:
                return DownloadResult(
                    title=book.title,
                    author=book.author or "Unknown",
                    filepath=None,
                    success=False,
                    error=f"No {format} format found",
                )

            # Download the book
            return self._download_single_book(best_match, target_dir, format)

        except LibrarianError as e:
            return DownloadResult(
                title=book.title,
                author=book.author or "Unknown",
                filepath=None,
                success=False,
                error=str(e),
            )
        except Exception as e:
            return DownloadResult(
                title=book.title,
                author=book.author or "Unknown",
                filepath=None,
                success=False,
                error=str(e),
            )

    def _download_parallel_with_timeout(
        self,
        books: List[BookRequest],
        target_dir: Path,
        format: str,
        parallel: int,
        progress_callback,
    ) -> List[DownloadResult]:
        """Download books in parallel with proper timeout and resource management."""
        results = []
        timeout_per_book = 300  # 5 minutes per book

        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=parallel
            ) as executor:
                future_to_book = {
                    executor.submit(
                        self._download_book_request, book, target_dir, format
                    ): book
                    for book in books
                }

                completed = 0
                for future in concurrent.futures.as_completed(
                    future_to_book, timeout=timeout_per_book * len(books)
                ):
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, len(books))

                    try:
                        result = future.result(timeout=timeout_per_book)
                        results.append(result)
                    except concurrent.futures.TimeoutError:
                        book = future_to_book[future]
                        self.logger.error(f"Download timed out for {book.title}")
                        future.cancel()  # Attempt to cancel the timed-out task
                        results.append(
                            DownloadResult(
                                title=book.title,
                                author=book.author or "Unknown",
                                filepath=None,
                                success=False,
                                error=f"Download timed out after {timeout_per_book} seconds",
                            )
                        )
                    except (LibrarianError, NetworkError, DownloadError) as exc:
                        book = future_to_book[future]
                        self.logger.error(f"Download failed for {book.title}: {exc}")
                        results.append(
                            DownloadResult(
                                title=book.title,
                                author=book.author or "Unknown",
                                filepath=None,
                                success=False,
                                error=str(exc),
                            )
                        )
                    except Exception as exc:
                        book = future_to_book[future]
                        self.logger.error(
                            f"Unexpected error downloading {book.title}: {exc}"
                        )
                        results.append(
                            DownloadResult(
                                title=book.title,
                                author=book.author or "Unknown",
                                filepath=None,
                                success=False,
                                error=f"Unexpected error: {exc}",
                            )
                        )

        except concurrent.futures.TimeoutError:
            self.logger.error(
                f"Overall batch download timed out after {timeout_per_book * len(books)} seconds"
            )
            # Fill remaining results with timeout errors
            for book in books[len(results) :]:
                results.append(
                    DownloadResult(
                        title=book.title,
                        author=book.author or "Unknown",
                        filepath=None,
                        success=False,
                        error="Batch download timed out",
                    )
                )
        except KeyboardInterrupt:
            self.logger.info("Download interrupted by user")
            # Fill remaining results with cancellation errors
            for book in books[len(results) :]:
                results.append(
                    DownloadResult(
                        title=book.title,
                        author=book.author or "Unknown",
                        filepath=None,
                        success=False,
                        error="Download cancelled by user",
                    )
                )
            raise

        return results

    def _create_safe_filename(self, title: str, format: str) -> str:
        """Create a safe filename for downloaded books."""
        # Remove invalid characters
        safe_title = "".join(
            c for c in title if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        safe_title = safe_title.replace(" ", "_")

        # Limit length
        if len(safe_title) > 100:
            safe_title = safe_title[:100]

        return f"{safe_title}.{format}"
