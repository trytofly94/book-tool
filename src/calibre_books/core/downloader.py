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
from typing import List, Optional, Dict, Any, Callable, NamedTuple
from dataclasses import dataclass

from ..utils.logging import LoggerMixin


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
        self.default_format = config.get('default_format', 'mobi')
        self.download_path = Path(config.get('download_path', '~/Downloads/Books')).expanduser()
        self.librarian_path = config.get('librarian_path', 'librarian')
        self.max_parallel = config.get('max_parallel', 1)
        self.quality = config.get('quality', 'high')
        
        # Ensure download directory exists
        self.download_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Initialized BookDownloader with download_path: {self.download_path}")

    def check_system_requirements(self) -> Dict[str, bool]:
        """Check if system requirements for downloading are met."""
        requirements = {
            'librarian': self._check_librarian(),
        }
        
        self.logger.info(f"System requirements check: {requirements}")
        return requirements

    def _check_librarian(self) -> bool:
        """Check if librarian CLI is available."""
        try:
            result = subprocess.run(
                [self.librarian_path, '--help'],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
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
            
        self.logger.info(f"Downloading books: series={series}, author={author}, title={title}")
        
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
                book for book in books_to_download 
                if book.get('format', '').lower() == format.lower()
            ]
            
            self.logger.info(f"Found {len(filtered_books)} books matching format {format}")
            
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
            self.logger.info(f"Download completed: {successful}/{len(results)} successful")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            raise

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
            # Parallel download
            with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
                future_to_book = {
                    executor.submit(self._download_book_request, book, target_dir, format): book 
                    for book in books
                }
                
                completed = 0
                for future in concurrent.futures.as_completed(future_to_book):
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, len(books))
                    
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as exc:
                        book = future_to_book[future]
                        self.logger.error(f"Download failed for {book.title}: {exc}")
                        results.append(DownloadResult(
                            title=book.title,
                            author=book.author or "Unknown",
                            filepath=None,
                            success=False,
                            error=str(exc)
                        ))
        
        successful = sum(1 for r in results if r.success)
        self.logger.info(f"Batch download completed: {successful}/{len(results)} successful")
        
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
                if not filename or '.' not in filename:
                    filename = "downloaded_book.epub"  # Default fallback
            
            output_path = target_dir / filename
            
            # Use wget or curl for direct download
            try:
                # Try wget first
                result = subprocess.run([
                    'wget', url, '-O', str(output_path)
                ], capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    # Fallback to curl
                    result = subprocess.run([
                        'curl', '-L', url, '-o', str(output_path)
                    ], capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    return DownloadResult(
                        title=filename,
                        author="Unknown",
                        filepath=None,
                        success=False,
                        error=f"Download failed: {result.stderr}"
                    )
                    
            except subprocess.TimeoutExpired:
                return DownloadResult(
                    title=filename,
                    author="Unknown", 
                    filepath=None,
                    success=False,
                    error="Download timed out"
                )
            
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
                    file_size=file_size
                )
            else:
                return DownloadResult(
                    title=filename,
                    author="Unknown",
                    filepath=None,
                    success=False,
                    error="Downloaded file is empty or missing"
                )
                
        except Exception as e:
            self.logger.error(f"URL download failed: {e}")
            return DownloadResult(
                title=filename or "Unknown",
                author="Unknown",
                filepath=None,
                success=False,
                error=str(e)
            )

    def parse_book_list(self, file_path: Path) -> List[BookRequest]:
        """
        Parse book list from file.
        
        File format: One book per line, either:
        - "Title" 
        - "Title|Author"
        - "Title|Author|Series"
        
        Args:
            file_path: Path to file containing book list
            
        Returns:
            List of book requests
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Book list file not found: {file_path}")
        
        books = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue  # Skip empty lines and comments
                    
                    parts = line.split('|')
                    
                    if len(parts) == 1:
                        # Just title
                        books.append(BookRequest(title=parts[0].strip()))
                    elif len(parts) == 2:
                        # Title and author
                        books.append(BookRequest(
                            title=parts[0].strip(),
                            author=parts[1].strip()
                        ))
                    elif len(parts) >= 3:
                        # Title, author, and series
                        books.append(BookRequest(
                            title=parts[0].strip(),
                            author=parts[1].strip(),
                            series=parts[2].strip()
                        ))
                    else:
                        self.logger.warning(f"Skipping invalid line {line_num}: {line}")
                        
        except Exception as e:
            self.logger.error(f"Failed to parse book list: {e}")
            raise ValueError(f"Failed to parse book list from {file_path}: {e}")
        
        self.logger.info(f"Parsed {len(books)} books from {file_path}")
        return books

    def _search_books(self, search_query: str, target_dir: Path) -> List[Dict[str, Any]]:
        """Search for books using librarian CLI."""
        try:
            # Run librarian search
            result = subprocess.run([
                self.librarian_path, '-p', str(target_dir), 'search', search_query
            ], capture_output=True, text=True, check=True, timeout=60)
            
            # Load search results from JSON file
            results_file = target_dir / 'search_results.json'
            if not results_file.exists():
                self.logger.warning("Search results file not found")
                return []
            
            with open(results_file, 'r') as f:
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

    def _download_single_book(self, book_data: Dict[str, Any], target_dir: Path, format: str) -> DownloadResult:
        """Download a single book from search results."""
        title = book_data.get('title', 'Unknown')
        author = book_data.get('author', 'Unknown')
        hash_id = book_data.get('hash', '')
        
        if not hash_id:
            return DownloadResult(
                title=title,
                author=author,
                filepath=None,
                success=False,
                error="No hash ID found"
            )
        
        # Create safe filename
        safe_filename = self._create_safe_filename(title, format)
        
        try:
            # Download using librarian
            result = subprocess.run([
                self.librarian_path, 'download', hash_id, safe_filename
            ], cwd=target_dir, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                return DownloadResult(
                    title=title,
                    author=author,
                    filepath=None,
                    success=False,
                    error=f"Download failed: {result.stderr}"
                )
            
            # Check if file was downloaded to Downloads folder and move it
            downloads_path = Path.home() / 'Downloads' / safe_filename
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
                    file_size=file_size
                )
            else:
                return DownloadResult(
                    title=title,
                    author=author,
                    filepath=None,
                    success=False,
                    error="Downloaded file not found"
                )
                
        except subprocess.TimeoutExpired:
            return DownloadResult(
                title=title,
                author=author,
                filepath=None,
                success=False,
                error="Download timed out"
            )
        except Exception as e:
            return DownloadResult(
                title=title,
                author=author,
                filepath=None,
                success=False,
                error=str(e)
            )

    def _download_book_request(self, book: BookRequest, target_dir: Path, format: str) -> DownloadResult:
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
                    error="No search results found"
                )
            
            # Find best match (first result with matching format)
            best_match = None
            for result in search_results:
                if result.get('format', '').lower() == format.lower():
                    best_match = result
                    break
            
            if not best_match:
                return DownloadResult(
                    title=book.title,
                    author=book.author or "Unknown",
                    filepath=None,
                    success=False,
                    error=f"No {format} format found"
                )
            
            # Download the book
            return self._download_single_book(best_match, target_dir, format)
            
        except Exception as e:
            return DownloadResult(
                title=book.title,
                author=book.author or "Unknown",
                filepath=None,
                success=False,
                error=str(e)
            )

    def _create_safe_filename(self, title: str, format: str) -> str:
        """Create a safe filename for downloaded books."""
        # Remove invalid characters
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')
        
        # Limit length
        if len(safe_title) > 100:
            safe_title = safe_title[:100]
        
        return f"{safe_title}.{format}"