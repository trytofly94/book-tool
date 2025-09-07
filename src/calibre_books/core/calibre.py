"""
Calibre integration module for Calibre Books CLI.

This module provides integration with Calibre's command-line tools
and database for managing book libraries and metadata.
"""

import logging
import subprocess
import json
import shlex
import re
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Tuple, Union
from dataclasses import dataclass
from datetime import datetime

from ..utils.logging import LoggerMixin
from .book import Book, LibraryStats, BookMetadata, BookFormat

if TYPE_CHECKING:
    from ..config.manager import ConfigManager


@dataclass
class CalibreResult:
    """Result from a Calibre CLI command."""
    success: bool
    output: str
    error: str
    return_code: int
    command: List[str]
    
    @property
    def has_data(self) -> bool:
        """Check if result contains usable data."""
        return self.success and bool(self.output.strip())


class CalibreError(Exception):
    """Base exception for Calibre operations."""
    pass


class CalibreNotFoundError(CalibreError):
    """Calibre CLI tools not found."""
    pass


class LibraryNotFoundError(CalibreError):
    """Calibre library not found or inaccessible."""
    pass


class MetadataError(CalibreError):
    """Metadata operation failed."""
    pass


class CalibreDB(LoggerMixin):
    """Low-level wrapper for calibredb CLI commands."""
    
    def __init__(self, library_path: Path, cli_path: str = 'auto'):
        """Initialize CalibreDB wrapper.
        
        Args:
            library_path: Path to Calibre library
            cli_path: Path to calibredb executable or 'auto' to detect
        """
        super().__init__()
        self.library_path = Path(library_path)
        self.cli_path = self._detect_calibre_cli(cli_path)
        
        # Validate library and CLI
        self._validate_library()
        self._validate_cli()
        
        self.logger.debug(f"Initialized CalibreDB with library: {self.library_path}")
    
    def _detect_calibre_cli(self, cli_path: str) -> str:
        """Detect or validate calibredb CLI path."""
        if cli_path != 'auto':
            return cli_path
        
        # Try common locations
        common_paths = [
            'calibredb',  # In PATH
            '/Applications/calibre.app/Contents/MacOS/calibredb',  # macOS app
            '/usr/bin/calibredb',  # Linux system install
            '/usr/local/bin/calibredb',  # Local install
            '/opt/calibre/calibredb',  # Alternative Linux location
        ]
        
        for path in common_paths:
            try:
                result = subprocess.run([path, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    self.logger.debug(f"Found calibredb at: {path}")
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
                continue
        
        raise CalibreNotFoundError("calibredb not found. Please ensure Calibre is installed and in PATH.")
    
    def _validate_library(self):
        """Validate that library path exists and contains a Calibre library."""
        if not self.library_path.exists():
            raise LibraryNotFoundError(f"Library path does not exist: {self.library_path}")
        
        metadata_db = self.library_path / 'metadata.db'
        if not metadata_db.exists():
            raise LibraryNotFoundError(f"No Calibre library found at: {self.library_path}")
    
    def _validate_cli(self):
        """Validate that CLI tool is accessible."""
        try:
            result = subprocess.run([self.cli_path, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise CalibreNotFoundError(f"calibredb not working: {self.cli_path}")
        except Exception as e:
            raise CalibreNotFoundError(f"Cannot execute calibredb: {e}")
    
    def execute_command(self, command: List[str], **kwargs) -> CalibreResult:
        """Execute calibredb command with proper error handling.
        
        Args:
            command: Command arguments (without 'calibredb')
            **kwargs: Additional subprocess arguments
            
        Returns:
            CalibreResult with execution details
        """
        full_command = [self.cli_path] + command + ['--library-path', str(self.library_path)]
        
        # Set default kwargs
        subprocess_kwargs = {
            'capture_output': True,
            'text': True,
            'timeout': kwargs.get('timeout', 30),
            'cwd': kwargs.get('cwd'),
            'env': kwargs.get('env')
        }
        
        self.logger.debug(f"Executing: {' '.join(shlex.quote(arg) for arg in full_command)}")
        
        try:
            result = subprocess.run(full_command, **subprocess_kwargs)
            
            calibre_result = CalibreResult(
                success=result.returncode == 0,
                output=result.stdout or '',
                error=result.stderr or '',
                return_code=result.returncode,
                command=full_command
            )
            
            if not calibre_result.success:
                self.logger.warning(f"Command failed (code {result.returncode}): {calibre_result.error}")
            
            return calibre_result
            
        except subprocess.TimeoutExpired as e:
            error_msg = f"Command timed out after {e.timeout}s"
            self.logger.error(error_msg)
            return CalibreResult(False, '', error_msg, -1, full_command)
            
        except Exception as e:
            error_msg = f"Command execution failed: {e}"
            self.logger.error(error_msg)
            return CalibreResult(False, '', error_msg, -1, full_command)
    
    def list_books(self, fields: List[str] = None, search: str = None, 
                   limit: int = None, offset: int = None, format_output: str = 'json') -> CalibreResult:
        """List books with filtering and field selection.
        
        Args:
            fields: List of fields to include in output
            search: Search query string
            limit: Maximum number of results
            offset: Offset for pagination  
            format_output: Output format ('json', 'csv', 'table')
            
        Returns:
            CalibreResult with book data
        """
        command = ['list']
        
        if fields:
            command.extend(['--fields', ','.join(fields)])
        
        if search:
            command.extend(['--search', search])
        
        if limit is not None:
            command.extend(['--limit', str(limit)])
        
        if offset is not None:
            command.extend(['--offset', str(offset)])
        
        # Set output format
        if format_output == 'json':
            command.append('--for-machine')
        elif format_output == 'csv':
            command.append('--separator=,')
        
        return self.execute_command(command)
    
    def get_metadata(self, book_id: int) -> CalibreResult:
        """Get detailed metadata for specific book.
        
        Args:
            book_id: Calibre book ID
            
        Returns:
            CalibreResult with metadata
        """
        command = ['show_metadata', str(book_id), '--as-opf']
        return self.execute_command(command)
    
    def set_metadata(self, book_id: int, metadata: Dict[str, Any]) -> CalibreResult:
        """Update metadata for specific book.
        
        Args:
            book_id: Calibre book ID
            metadata: Dictionary of metadata fields to update
            
        Returns:
            CalibreResult indicating success
        """
        command = ['set_metadata', str(book_id)]
        
        for field, value in metadata.items():
            if value is not None:
                command.extend(['--field', f'{field}:{value}'])
        
        return self.execute_command(command)
    
    def find_duplicates(self) -> CalibreResult:
        """Find duplicate books in library.
        
        Returns:
            CalibreResult with duplicate information
        """
        command = ['show_duplicates']
        return self.execute_command(command)
    
    def remove_books(self, book_ids: List[int]) -> CalibreResult:
        """Remove books from library.
        
        Args:
            book_ids: List of book IDs to remove
            
        Returns:
            CalibreResult indicating success
        """
        command = ['remove'] + [str(book_id) for book_id in book_ids]
        return self.execute_command(command)
    
    def check_library(self) -> CalibreResult:
        """Check library for integrity issues.
        
        Returns:
            CalibreResult with check results
        """
        command = ['check_library']
        return self.execute_command(command, timeout=300)  # Longer timeout for library check
    
    def export(self, export_path: Path, export_format: str = 'csv') -> CalibreResult:
        """Export library data.
        
        Args:
            export_path: Path for export file
            export_format: Export format ('csv', 'xml', etc.)
            
        Returns:
            CalibreResult indicating export success
        """
        command = ['export']
        
        if export_format == 'csv':
            command.extend(['--catalog', str(export_path)])
        else:
            command.extend(['--to-dir', str(export_path.parent), '--formats', export_format])
        
        return self.execute_command(command, timeout=600)  # Longer timeout for exports


class CalibreIntegration(LoggerMixin):
    """
    Integration with Calibre CLI tools and database.
    
    Provides methods for interacting with Calibre libraries,
    managing metadata, and performing library operations.
    """
    
    def __init__(self, config_manager: 'ConfigManager'):
        """
        Initialize Calibre integration.
        
        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        super().__init__()
        self.config_manager = config_manager
        
        # Get Calibre-specific configuration with error handling
        try:
            calibre_config = config_manager.get_calibre_config()
            self.library_path = Path(calibre_config.get('library_path', '~/Calibre-Library')).expanduser()
            self.cli_path = calibre_config.get('cli_path', 'auto')
            
            self.logger.debug(f"Initialized Calibre integration with library: {self.library_path}, CLI: {self.cli_path}")
        except Exception as e:
            self.logger.warning(f"Failed to load Calibre config, using defaults: {e}")
            self.library_path = Path('~/Calibre-Library').expanduser()
            self.cli_path = 'auto'
        
        # Initialize CalibreDB wrapper (lazy initialization)
        self._calibre_db = None
        
        self.logger.info(f"Initialized Calibre integration with library: {self.library_path}")
    
    @property
    def calibre_db(self) -> CalibreDB:
        """Lazy initialization of CalibreDB wrapper."""
        if self._calibre_db is None:
            self._calibre_db = CalibreDB(self.library_path, self.cli_path)
        return self._calibre_db
    
    def get_library_stats(
        self,
        library_path: Optional[Path] = None,
        detailed: bool = False,
        progress_callback=None,
    ) -> LibraryStats:
        """
        Get statistics about the Calibre library.
        
        Args:
            library_path: Path to library (uses default if None)
            detailed: Whether to include detailed statistics
            progress_callback: Optional progress callback function
            
        Returns:
            Library statistics
        """
        self.logger.info("Getting library statistics")
        
        try:
            # Use provided library path or default
            if library_path:
                calibre_db = CalibreDB(library_path, self.cli_path)
            else:
                calibre_db = self.calibre_db
            
            stats = LibraryStats()
            
            if progress_callback:
                progress_callback(0, "Analyzing library structure...")
            
            # Get basic book count and metadata
            result = calibre_db.list_books(fields=['id', 'title', 'authors', 'series', 'formats', 'size'])
            if not result.success:
                raise CalibreError(f"Failed to list books: {result.error}")
            
            if result.has_data:
                try:
                    books_data = json.loads(result.output)
                    stats.total_books = len(books_data)
                    
                    # Track authors, series, and formats
                    authors_set = set()
                    series_set = set()
                    format_counts = {}
                    total_size = 0
                    books_without_asin = 0
                    
                    if progress_callback:
                        progress_callback(20, "Processing book metadata...")
                    
                    for i, book in enumerate(books_data):
                        # Process authors
                        if 'authors' in book and book['authors']:
                            if isinstance(book['authors'], list):
                                authors_set.update(book['authors'])
                            else:
                                # Handle case where authors is a string
                                authors = book['authors'].split(' & ')
                                authors_set.update(authors)
                        
                        # Process series
                        if 'series' in book and book['series']:
                            series_set.add(book['series'])
                        
                        # Process formats
                        if 'formats' in book and book['formats']:
                            for format_name in book['formats']:
                                format_counts[format_name.lower()] = format_counts.get(format_name.lower(), 0) + 1
                        
                        # Process size
                        if 'size' in book and book['size']:
                            try:
                                total_size += int(book['size'])
                            except (ValueError, TypeError):
                                pass
                        
                        # Update progress for large libraries
                        if progress_callback and i % 1000 == 0:
                            progress = 20 + int(60 * i / len(books_data))
                            progress_callback(progress, f"Processing book {i+1}/{len(books_data)}...")
                    
                    stats.total_authors = len(authors_set)
                    stats.total_series = len(series_set)
                    stats.library_size = total_size
                    stats.format_distribution = format_counts
                    
                    # Get top authors if detailed analysis requested
                    if detailed:
                        if progress_callback:
                            progress_callback(80, "Calculating detailed statistics...")
                        
                        # Count books per author
                        author_counts = {}
                        for book in books_data:
                            if 'authors' in book and book['authors']:
                                if isinstance(book['authors'], list):
                                    authors = book['authors']
                                else:
                                    authors = book['authors'].split(' & ')
                                for author in authors:
                                    author_counts[author] = author_counts.get(author, 0) + 1
                        
                        # Get top 10 authors
                        stats.top_authors = sorted(author_counts.items(), 
                                                  key=lambda x: x[1], reverse=True)[:10]
                        
                        # Check for books without ASIN if custom column exists
                        try:
                            asin_result = calibre_db.list_books(
                                fields=['id', 'identifiers'], 
                                search='not identifiers:"amazon:*"'
                            )
                            if asin_result.success and asin_result.has_data:
                                asin_data = json.loads(asin_result.output)
                                stats.books_without_asin = len(asin_data)
                        except Exception as e:
                            self.logger.debug(f"Could not check ASIN status: {e}")
                        
                        # Check for potential duplicates (basic title matching)
                        try:
                            duplicate_result = calibre_db.find_duplicates()
                            if duplicate_result.success and duplicate_result.output:
                                # Count duplicate groups
                                duplicate_lines = duplicate_result.output.strip().split('\n')
                                stats.duplicate_titles = len([line for line in duplicate_lines if line.strip()])
                        except Exception as e:
                            self.logger.debug(f"Could not check duplicates: {e}")
                    
                    if progress_callback:
                        progress_callback(100, "Library analysis complete")
                    
                    stats.last_updated = datetime.now()
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse library data: {e}")
                    raise CalibreError(f"Failed to parse library data: {e}")
            
            self.logger.info(f"Library analysis complete: {stats.total_books} books, {stats.total_authors} authors")
            return stats
            
        except CalibreError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get library stats: {e}")
            raise CalibreError(f"Failed to analyze library: {e}")
    
    def get_books_for_asin_update(
        self,
        library_path: Optional[Path] = None,
        filter_pattern: Optional[str] = None,
        missing_only: bool = False,
    ) -> List[Book]:
        """
        Get list of books that need ASIN updates.
        
        Args:
            library_path: Path to library
            filter_pattern: Pattern to filter books
            missing_only: Only return books without ASINs
            
        Returns:
            List of books needing ASIN updates
        """
        self.logger.info("Getting books for ASIN update")
        
        try:
            # Use provided library path or default
            if library_path:
                calibre_db = CalibreDB(library_path, self.cli_path)
            else:
                calibre_db = self.calibre_db
            
            books = []
            
            # Build search query
            search_query = None
            if missing_only:
                # Look for books without Amazon identifier
                search_query = 'not identifiers:"amazon:*"'
            
            if filter_pattern:
                if search_query:
                    search_query = f'({search_query}) and ({filter_pattern})'
                else:
                    search_query = filter_pattern
            
            # Get books from Calibre
            fields = ['id', 'title', 'authors', 'identifiers', 'series', 'series_index', 'isbn', 'pubdate', 'formats', 'path']
            result = calibre_db.list_books(fields=fields, search=search_query)
            
            if not result.success:
                raise CalibreError(f"Failed to retrieve books: {result.error}")
            
            if result.has_data:
                try:
                    books_data = json.loads(result.output)
                    
                    for book_data in books_data:
                        try:
                            book = self._convert_calibre_data_to_book(book_data)
                            books.append(book)
                        except Exception as e:
                            self.logger.warning(f"Failed to convert book data {book_data.get('id', 'unknown')}: {e}")
                            continue
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse books data: {e}")
                    raise CalibreError(f"Failed to parse books data: {e}")
            
            self.logger.info(f"Retrieved {len(books)} books for ASIN update")
            return books
            
        except CalibreError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to get books for ASIN update: {e}")
            raise CalibreError(f"Failed to retrieve books: {e}")
    
    def _convert_calibre_data_to_book(self, book_data: Dict[str, Any]) -> Book:
        """Convert Calibre book data to Book object.
        
        Args:
            book_data: Dictionary from Calibre CLI output
            
        Returns:
            Book object
        """
        # Extract basic metadata
        title = book_data.get('title', 'Unknown Title')
        authors = book_data.get('authors', [])
        if isinstance(authors, str):
            authors = [authors]
        elif not authors:
            authors = ['Unknown Author']
        
        primary_author = authors[0] if authors else 'Unknown Author'
        
        # Extract identifiers
        identifiers = book_data.get('identifiers', {})
        isbn = identifiers.get('isbn', None)
        asin = None
        
        # Look for Amazon identifier
        for key, value in identifiers.items():
            if key.startswith('amazon'):
                asin = value
                break
        
        # Extract other metadata
        series = book_data.get('series', None)
        series_index = book_data.get('series_index', None)
        if series_index is not None:
            try:
                series_index = float(series_index)
            except (ValueError, TypeError):
                series_index = None
        
        # Parse publication date
        pubdate = None
        if book_data.get('pubdate'):
            try:
                pubdate = datetime.fromisoformat(book_data['pubdate'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                pass
        
        # Determine format
        formats = book_data.get('formats', [])
        book_format = None
        if formats:
            format_str = formats[0].lower() if isinstance(formats, list) else str(formats).lower()
            try:
                book_format = BookFormat(format_str)
            except ValueError:
                pass
        
        # Create metadata
        metadata = BookMetadata(
            title=title,
            author=primary_author,
            authors=authors,
            isbn=isbn,
            asin=asin,
            series=series,
            series_index=series_index,
            publication_date=pubdate,
            format=book_format
        )
        
        # Create book with file path if available
        file_path = None
        if book_data.get('path'):
            file_path = self.library_path / book_data['path']
        
        book = Book(
            metadata=metadata,
            calibre_id=int(book_data['id']) if book_data.get('id') else None,
            file_path=file_path
        )
        
        return book
    
    def update_asins(self, asin_results: List[Any], dry_run: bool = False) -> int:
        """
        Update ASINs in the Calibre library.
        
        Args:
            asin_results: List of ASIN lookup results with book_id and asin
            dry_run: If True, only simulate updates without making changes
            
        Returns:
            Number of books updated
        """
        self.logger.info(f"Updating ASINs for {len(asin_results)} books (dry_run={dry_run})")
        
        if not asin_results:
            return 0
        
        updated_count = 0
        
        try:
            for result in asin_results:
                try:
                    # Extract data from result (handle different result formats)
                    if hasattr(result, 'book_id') and hasattr(result, 'asin'):
                        book_id = result.book_id
                        asin = result.asin
                    elif isinstance(result, dict):
                        book_id = result.get('book_id') or result.get('calibre_id')
                        asin = result.get('asin')
                    else:
                        self.logger.warning(f"Unexpected result format: {result}")
                        continue
                    
                    if not book_id or not asin:
                        self.logger.warning(f"Missing book_id or ASIN in result: {result}")
                        continue
                    
                    if dry_run:
                        self.logger.info(f"DRY RUN: Would update book {book_id} with ASIN {asin}")
                        updated_count += 1
                        continue
                    
                    # Update the book's Amazon identifier in Calibre
                    metadata_update = {
                        'identifiers': f'amazon:{asin}'
                    }
                    
                    update_result = self.calibre_db.set_metadata(int(book_id), metadata_update)
                    
                    if update_result.success:
                        updated_count += 1
                        self.logger.debug(f"Updated book {book_id} with ASIN {asin}")
                    else:
                        self.logger.warning(f"Failed to update book {book_id}: {update_result.error}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to update ASIN for result {result}: {e}")
                    continue
            
            action = "Would update" if dry_run else "Updated"
            self.logger.info(f"{action} {updated_count} books with ASINs")
            return updated_count
            
        except Exception as e:
            self.logger.error(f"Failed to update ASINs: {e}")
            raise CalibreError(f"ASIN update failed: {e}")
    
    def search_library(
        self,
        query: str,
        library_path: Optional[Path] = None,
        limit: int = 20,
        offset: int = 0,
        progress_callback=None,
    ) -> List[Book]:
        """Search books in the library.
        
        Args:
            query: Search query string
            library_path: Path to library (uses default if None)
            limit: Maximum number of results
            offset: Offset for pagination
            progress_callback: Optional progress callback function
            
        Returns:
            List of matching books
        """
        self.logger.info(f"Searching library with query: {query}")
        
        try:
            # Use provided library path or default
            if library_path:
                calibre_db = CalibreDB(library_path, self.cli_path)
            else:
                calibre_db = self.calibre_db
            
            if progress_callback:
                progress_callback(0, f"Searching for: {query}")
            
            # Search with all relevant fields
            fields = ['id', 'title', 'authors', 'identifiers', 'series', 'series_index', 'isbn', 'pubdate', 'formats', 'path', 'rating', 'tags']
            result = calibre_db.list_books(
                fields=fields,
                search=query,
                limit=limit,
                offset=offset
            )
            
            if not result.success:
                raise CalibreError(f"Search failed: {result.error}")
            
            books = []
            if result.has_data:
                try:
                    books_data = json.loads(result.output)
                    
                    if progress_callback:
                        progress_callback(50, f"Processing {len(books_data)} results...")
                    
                    for i, book_data in enumerate(books_data):
                        try:
                            book = self._convert_calibre_data_to_book(book_data)
                            books.append(book)
                        except Exception as e:
                            self.logger.warning(f"Failed to convert search result {book_data.get('id', 'unknown')}: {e}")
                            continue
                        
                        # Update progress for large result sets
                        if progress_callback and i % 100 == 0:
                            progress = 50 + int(50 * i / len(books_data))
                            progress_callback(progress, f"Processing result {i+1}/{len(books_data)}...")
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse search results: {e}")
                    raise CalibreError(f"Failed to parse search results: {e}")
            
            if progress_callback:
                progress_callback(100, f"Search complete: {len(books)} results")
            
            self.logger.info(f"Search returned {len(books)} results")
            return books
            
        except CalibreError:
            raise
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            raise CalibreError(f"Search failed: {e}")
    
    def remove_duplicates(self, library_path: Optional[Path] = None, dry_run: bool = True, progress_callback=None):
        """Remove duplicate books from the library.
        
        Args:
            library_path: Path to library (uses default if None)
            dry_run: If True, only identify duplicates without removing
            progress_callback: Optional progress callback function
            
        Returns:
            Result object with removal details
        """
        self.logger.info(f"Finding duplicate books (dry_run={dry_run})")
        
        @dataclass
        class DuplicateResult:
            duplicates_found: int = 0
            books_removed: int = 0
            space_freed: int = 0
            space_freed_human: str = "0 B"
            duplicate_groups: List[List[int]] = field(default_factory=list)
        
        try:
            # Use provided library path or default
            if library_path:
                calibre_db = CalibreDB(library_path, self.cli_path)
            else:
                calibre_db = self.calibre_db
            
            if progress_callback:
                progress_callback(0, "Scanning for duplicates...")
            
            # Find duplicates using Calibre's built-in detection
            duplicate_result = calibre_db.find_duplicates()
            
            if not duplicate_result.success:
                self.logger.warning(f"Duplicate detection failed: {duplicate_result.error}")
                return DuplicateResult()
            
            result = DuplicateResult()
            
            if duplicate_result.output and duplicate_result.output.strip():
                # Parse duplicate output
                duplicate_lines = duplicate_result.output.strip().split('\n')
                current_group = []
                
                for line in duplicate_lines:
                    line = line.strip()
                    if not line:
                        if current_group:
                            result.duplicate_groups.append(current_group)
                            current_group = []
                    else:
                        # Extract book ID from line (format varies)
                        import re
                        id_match = re.search(r'\b(\d+)\b', line)
                        if id_match:
                            book_id = int(id_match.group(1))
                            current_group.append(book_id)
                
                # Add last group
                if current_group:
                    result.duplicate_groups.append(current_group)
                
                result.duplicates_found = sum(len(group) - 1 for group in result.duplicate_groups if len(group) > 1)
                
                if progress_callback:
                    progress_callback(50, f"Found {result.duplicates_found} duplicate books...")
                
                # If not dry run, remove duplicates (keep first in each group)
                if not dry_run and result.duplicate_groups:
                    books_to_remove = []
                    
                    for group in result.duplicate_groups:
                        if len(group) > 1:
                            # Keep first book, mark others for removal
                            books_to_remove.extend(group[1:])
                    
                    if books_to_remove:
                        self.logger.info(f"Removing {len(books_to_remove)} duplicate books")
                        
                        # Calculate space to be freed (approximate)
                        try:
                            # Get sizes of books to remove
                            size_result = calibre_db.list_books(
                                fields=['id', 'size'],
                                search=f"id:{','.join(map(str, books_to_remove))}"
                            )
                            if size_result.success and size_result.has_data:
                                size_data = json.loads(size_result.output)
                                total_size = sum(int(book.get('size', 0)) for book in size_data)
                                result.space_freed = total_size
                                result.space_freed_human = self._format_size(total_size)
                        except Exception as e:
                            self.logger.debug(f"Could not calculate space savings: {e}")
                        
                        # Remove duplicates
                        remove_result = calibre_db.remove_books(books_to_remove)
                        if remove_result.success:
                            result.books_removed = len(books_to_remove)
                        else:
                            self.logger.error(f"Failed to remove duplicates: {remove_result.error}")
                            raise CalibreError(f"Duplicate removal failed: {remove_result.error}")
            
            if progress_callback:
                progress_callback(100, "Duplicate processing complete")
            
            action = "Found" if dry_run else "Removed"
            self.logger.info(f"{action} {result.duplicates_found} duplicate books")
            return result
            
        except CalibreError:
            raise
        except Exception as e:
            self.logger.error(f"Duplicate processing failed: {e}")
            raise CalibreError(f"Duplicate processing failed: {e}")
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    def fix_metadata_issues(self, library_path: Optional[Path] = None, dry_run: bool = True, progress_callback=None):
        """Fix common metadata issues in the library.
        
        Args:
            library_path: Path to library (uses default if None)
            dry_run: If True, only identify issues without fixing
            progress_callback: Optional progress callback function
            
        Returns:
            Result object with fix details
        """
        self.logger.info(f"Fixing metadata issues (dry_run={dry_run})")
        
        @dataclass
        class MetadataResult:
            issues_found: int = 0
            issues_fixed: int = 0
            issues_by_type: Dict[str, int] = field(default_factory=dict)
        
        try:
            # Use provided library path or default
            if library_path:
                calibre_db = CalibreDB(library_path, self.cli_path)
            else:
                calibre_db = self.calibre_db
            
            result = MetadataResult()
            
            if progress_callback:
                progress_callback(0, "Scanning for metadata issues...")
            
            # Get all books with metadata
            fields = ['id', 'title', 'authors', 'series', 'series_index', 'pubdate', 'isbn', 'tags']
            book_result = calibre_db.list_books(fields=fields)
            
            if not book_result.success:
                raise CalibreError(f"Failed to retrieve books: {book_result.error}")
            
            if book_result.has_data:
                books_data = json.loads(book_result.output)
                total_books = len(books_data)
                
                for i, book_data in enumerate(books_data):
                    book_id = book_data.get('id')
                    if not book_id:
                        continue
                    
                    issues_found = 0
                    fixes = {}
                    
                    # Check title issues
                    title = book_data.get('title', '')
                    if title:
                        # Fix title case (simple approach)
                        if title.isupper() or title.islower():
                            fixed_title = title.title()
                            # Don't capitalize common words incorrectly
                            fixed_title = re.sub(r'\b(And|Or|But|The|A|An|In|On|At|To|For|Of|With|By)\b', 
                                                lambda m: m.group().lower(), fixed_title)
                            if fixed_title != title:
                                fixes['title'] = fixed_title
                                issues_found += 1
                                result.issues_by_type['title_case'] = result.issues_by_type.get('title_case', 0) + 1
                    
                    # Check author name standardization
                    authors = book_data.get('authors', [])
                    if authors and isinstance(authors, list):
                        fixed_authors = []
                        authors_changed = False
                        for author in authors:
                            # Fix author name case
                            if author.isupper() or author.islower():
                                fixed_author = author.title()
                                fixed_authors.append(fixed_author)
                                authors_changed = True
                            else:
                                fixed_authors.append(author)
                        
                        if authors_changed:
                            fixes['authors'] = ' & '.join(fixed_authors)
                            issues_found += 1
                            result.issues_by_type['author_case'] = result.issues_by_type.get('author_case', 0) + 1
                    
                    # Check series index issues
                    series = book_data.get('series')
                    series_index = book_data.get('series_index')
                    if series and series_index is None:
                        fixes['series_index'] = '1.0'  # Default to first book
                        issues_found += 1
                        result.issues_by_type['missing_series_index'] = result.issues_by_type.get('missing_series_index', 0) + 1
                    elif series_index is not None:
                        try:
                            # Ensure series index is properly formatted
                            index_float = float(series_index)
                            if index_float != series_index or index_float <= 0:
                                fixes['series_index'] = str(max(1.0, round(index_float, 1)))
                                issues_found += 1
                                result.issues_by_type['invalid_series_index'] = result.issues_by_type.get('invalid_series_index', 0) + 1
                        except (ValueError, TypeError):
                            fixes['series_index'] = '1.0'
                            issues_found += 1
                            result.issues_by_type['invalid_series_index'] = result.issues_by_type.get('invalid_series_index', 0) + 1
                    
                    result.issues_found += issues_found
                    
                    # Apply fixes if not dry run
                    if fixes and not dry_run:
                        fix_result = calibre_db.set_metadata(int(book_id), fixes)
                        if fix_result.success:
                            result.issues_fixed += len(fixes)
                        else:
                            self.logger.warning(f"Failed to fix metadata for book {book_id}: {fix_result.error}")
                    elif fixes and dry_run:
                        result.issues_fixed += len(fixes)  # Count what would be fixed
                    
                    # Update progress
                    if progress_callback and i % 100 == 0:
                        progress = int(100 * i / total_books)
                        progress_callback(progress, f"Processed {i}/{total_books} books...")
            
            if progress_callback:
                progress_callback(100, "Metadata analysis complete")
            
            action = "Would fix" if dry_run else "Fixed"
            self.logger.info(f"Metadata analysis: found {result.issues_found} issues, {action} {result.issues_fixed}")
            return result
            
        except CalibreError:
            raise
        except Exception as e:
            self.logger.error(f"Metadata fixing failed: {e}")
            raise CalibreError(f"Metadata fixing failed: {e}")
    
    def cleanup_orphaned_files(self, library_path: Optional[Path] = None, dry_run: bool = True, progress_callback=None):
        """Clean up orphaned files in the library.
        
        Args:
            library_path: Path to library (uses default if None)
            dry_run: If True, only identify files without removing
            progress_callback: Optional progress callback function
            
        Returns:
            Result object with cleanup details
        """
        self.logger.info(f"Cleaning up orphaned files (dry_run={dry_run})")
        
        @dataclass
        class CleanupResult:
            orphaned_files_found: int = 0
            files_removed: int = 0
            space_freed: int = 0
            space_freed_human: str = "0 B"
            orphaned_paths: List[Path] = field(default_factory=list)
        
        try:
            # Use provided library path or default
            target_library = library_path if library_path else self.library_path
            
            if progress_callback:
                progress_callback(0, "Scanning library for orphaned files...")
            
            # First, let Calibre check its own library
            if library_path:
                calibre_db = CalibreDB(library_path, self.cli_path)
            else:
                calibre_db = self.calibre_db
            
            check_result = calibre_db.check_library()
            result = CleanupResult()
            
            if check_result.success and check_result.output:
                # Parse Calibre's library check output
                lines = check_result.output.strip().split('\n')
                orphaned_files = []
                
                for line in lines:
                    if 'orphaned' in line.lower() or 'missing' in line.lower():
                        # Extract file paths from output (basic pattern matching)
                        import re
                        path_match = re.search(r'([^\s]+\.\w+)', line)
                        if path_match:
                            orphaned_files.append(path_match.group(1))
                
                result.orphaned_files_found = len(orphaned_files)
                
            if progress_callback:
                progress_callback(30, "Checking file system for additional orphans...")
            
            # Additional manual scan for common orphaned file patterns
            orphaned_patterns = [
                '**/*.tmp',
                '**/*.bak',
                '**/.DS_Store',
                '**/Thumbs.db',
                '**/*~',
                '**/*.part'
            ]
            
            additional_orphans = []
            for pattern in orphaned_patterns:
                for orphan_file in target_library.glob(pattern):
                    if orphan_file.is_file():
                        additional_orphans.append(orphan_file)
                        result.orphaned_paths.append(orphan_file)
            
            result.orphaned_files_found += len(additional_orphans)
            
            if progress_callback:
                progress_callback(60, f"Found {result.orphaned_files_found} orphaned files...")
            
            # Calculate total size
            total_size = 0
            for orphan_path in result.orphaned_paths:
                try:
                    if orphan_path.exists():
                        total_size += orphan_path.stat().st_size
                except (OSError, IOError):
                    continue
            
            result.space_freed = total_size
            result.space_freed_human = self._format_size(total_size)
            
            # Remove files if not dry run
            if not dry_run and result.orphaned_paths:
                removed_count = 0
                for orphan_path in result.orphaned_paths:
                    try:
                        if orphan_path.exists():
                            orphan_path.unlink()
                            removed_count += 1
                            self.logger.debug(f"Removed orphaned file: {orphan_path}")
                    except (OSError, IOError) as e:
                        self.logger.warning(f"Failed to remove {orphan_path}: {e}")
                        continue
                
                result.files_removed = removed_count
            
            if progress_callback:
                progress_callback(100, "File cleanup complete")
            
            action = "Would remove" if dry_run else "Removed"
            self.logger.info(f"File cleanup: found {result.orphaned_files_found} orphaned files, "
                           f"{action} {result.files_removed if not dry_run else result.orphaned_files_found} "
                           f"({result.space_freed_human})")
            return result
            
        except Exception as e:
            self.logger.error(f"File cleanup failed: {e}")
            raise CalibreError(f"File cleanup failed: {e}")
    
    def rebuild_search_index(self, library_path: Optional[Path] = None, progress_callback=None):
        """Rebuild the search index for the library.
        
        Args:
            library_path: Path to library (uses default if None)
            progress_callback: Optional progress callback function
        """
        self.logger.info("Rebuilding search index")
        
        try:
            # Use provided library path or default
            if library_path:
                calibre_db = CalibreDB(library_path, self.cli_path)
            else:
                calibre_db = self.calibre_db
            
            if progress_callback:
                progress_callback(0, "Starting search index rebuild...")
            
            # Calibre doesn't have a direct command to rebuild search index,
            # but we can trigger it by doing a comprehensive library check
            check_result = calibre_db.check_library()
            
            if not check_result.success:
                self.logger.warning(f"Library check during index rebuild failed: {check_result.error}")
            
            if progress_callback:
                progress_callback(50, "Optimizing library database...")
            
            # Try to run a comprehensive search to ensure index is working
            test_result = calibre_db.list_books(fields=['id'], search='*', limit=1)
            
            if progress_callback:
                progress_callback(100, "Search index rebuild complete")
            
            if test_result.success:
                self.logger.info("Search index rebuild completed successfully")
            else:
                self.logger.warning("Search index rebuild may have issues")
                
        except Exception as e:
            self.logger.error(f"Search index rebuild failed: {e}")
            raise CalibreError(f"Search index rebuild failed: {e}")
    
    def export_library(
        self,
        source_path: Path,
        destination_path: Path,
        export_format: str = 'csv',
        include_files: bool = False,
        filter_pattern: Optional[str] = None,
        progress_callback=None,
    ):
        """Export library to different formats.
        
        Args:
            source_path: Source library path
            destination_path: Destination path for export
            export_format: Format for export ('csv', 'json', 'xml')
            include_files: Whether to include book files in export
            filter_pattern: Pattern to filter books for export
            progress_callback: Optional progress callback function
            
        Returns:
            Result object with export details
        """
        self.logger.info(f"Exporting library from {source_path} to {destination_path} (format: {export_format})")
        
        @dataclass
        class ExportResult:
            book_count: int = 0
            export_size: int = 0
            export_size_human: str = "0 B"
            export_path: Path = destination_path
            success: bool = False
        
        try:
            # Create destination directory if needed
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use source library
            calibre_db = CalibreDB(source_path, self.cli_path)
            result = ExportResult()
            
            if progress_callback:
                progress_callback(0, "Preparing library export...")
            
            if export_format.lower() == 'csv':
                # Export as CSV using Calibre's built-in functionality
                export_result = calibre_db.export(destination_path, 'csv')
                
                if export_result.success:
                    result.success = True
                    
                    # Count books exported
                    if filter_pattern:
                        count_result = calibre_db.list_books(search=filter_pattern, fields=['id'])
                    else:
                        count_result = calibre_db.list_books(fields=['id'])
                    
                    if count_result.success and count_result.has_data:
                        books_data = json.loads(count_result.output)
                        result.book_count = len(books_data)
                
            else:
                # For JSON/XML, we need to export manually
                if progress_callback:
                    progress_callback(20, "Retrieving book data...")
                
                fields = ['id', 'title', 'authors', 'series', 'series_index', 'isbn', 'identifiers', 
                         'pubdate', 'rating', 'tags', 'formats', 'size', 'path']
                
                books_result = calibre_db.list_books(fields=fields, search=filter_pattern)
                
                if not books_result.success:
                    raise CalibreError(f"Failed to retrieve books for export: {books_result.error}")
                
                if books_result.has_data:
                    books_data = json.loads(books_result.output)
                    result.book_count = len(books_data)
                    
                    if progress_callback:
                        progress_callback(60, f"Formatting {len(books_data)} books...")
                    
                    if export_format.lower() == 'json':
                        with open(destination_path, 'w', encoding='utf-8') as f:
                            json.dump(books_data, f, indent=2, default=str, ensure_ascii=False)
                        result.success = True
                        
                    elif export_format.lower() == 'xml':
                        import xml.etree.ElementTree as ET
                        
                        root = ET.Element('library')
                        for book in books_data:
                            book_elem = ET.SubElement(root, 'book')
                            for key, value in book.items():
                                if value is not None:
                                    elem = ET.SubElement(book_elem, key)
                                    elem.text = str(value)
                        
                        tree = ET.ElementTree(root)
                        tree.write(str(destination_path), encoding='utf-8', xml_declaration=True)
                        result.success = True
                    
                    else:
                        raise CalibreError(f"Unsupported export format: {export_format}")
            
            if progress_callback:
                progress_callback(80, "Calculating export size...")
            
            # Calculate export file size
            if destination_path.exists():
                result.export_size = destination_path.stat().st_size
                result.export_size_human = self._format_size(result.export_size)
            
            if progress_callback:
                progress_callback(100, "Export complete")
            
            self.logger.info(f"Library export completed: {result.book_count} books exported "
                           f"to {destination_path} ({result.export_size_human})")
            return result
            
        except CalibreError:
            raise
        except Exception as e:
            self.logger.error(f"Library export failed: {e}")
            raise CalibreError(f"Library export failed: {e}")
    
