"""
Book data models for Calibre Books CLI.

This module defines the core data structures for representing books,
metadata, and related information throughout the application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, validator


class BookFormat(Enum):
    """Supported book formats."""
    MOBI = "mobi"
    EPUB = "epub"
    PDF = "pdf"
    AZW = "azw"
    AZW3 = "azw3"
    KFX = "kfx"
    TXT = "txt"
    RTF = "rtf"
    HTML = "html"
    DOCX = "docx"


class BookStatus(Enum):
    """Book processing status."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    CONVERTING = "converting"
    CONVERTED = "converted"
    FAILED = "failed"
    COMPLETED = "completed"


class BookMetadata(BaseModel):
    """
    Comprehensive book metadata model.
    
    Uses Pydantic for validation and serialization.
    """
    title: str = Field(..., min_length=1, description="Book title")
    author: str = Field(..., min_length=1, description="Primary author")
    authors: List[str] = Field(default_factory=list, description="All authors")
    isbn: Optional[str] = Field(None, description="ISBN-10 or ISBN-13")
    asin: Optional[str] = Field(None, description="Amazon ASIN")
    series: Optional[str] = Field(None, description="Series name")
    series_index: Optional[float] = Field(None, description="Position in series")
    publisher: Optional[str] = Field(None, description="Publisher name")
    publication_date: Optional[datetime] = Field(None, description="Publication date")
    language: str = Field(default="en", description="Book language code")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating (1-5 stars)")
    tags: List[str] = Field(default_factory=list, description="Book tags/genres")
    description: Optional[str] = Field(None, description="Book description/synopsis")
    cover_url: Optional[str] = Field(None, description="Cover image URL")
    page_count: Optional[int] = Field(None, ge=1, description="Number of pages")
    word_count: Optional[int] = Field(None, ge=1, description="Number of words")
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    format: Optional[BookFormat] = Field(None, description="Book format")
    
    @validator('authors', pre=True)
    def ensure_authors_list(cls, v, values):
        """Ensure authors list includes the primary author."""
        if isinstance(v, str):
            v = [v]
        if 'author' in values and values['author'] not in v:
            v.insert(0, values['author'])
        return v
    
    @validator('asin')
    def validate_asin_format(cls, v):
        """Validate ASIN format if provided."""
        if v is not None:
            from ..utils.validation import validate_asin
            if not validate_asin(v):
                raise ValueError("Invalid ASIN format")
        return v
    
    @validator('isbn')
    def validate_isbn_format(cls, v):
        """Validate ISBN format if provided."""
        if v is not None:
            from ..utils.validation import validate_isbn
            is_valid, normalized = validate_isbn(v)
            if not is_valid:
                raise ValueError("Invalid ISBN format")
            return normalized
        return v


@dataclass
class Book:
    """
    Main book data class with file system information.
    
    Combines metadata with file system paths and processing status.
    """
    metadata: BookMetadata
    file_path: Optional[Path] = None
    calibre_id: Optional[int] = None
    status: BookStatus = BookStatus.PENDING
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if self.file_path:
            self.file_path = Path(self.file_path).resolve()
    
    @property
    def title(self) -> str:
        """Convenience property for book title."""
        return self.metadata.title
    
    @property
    def author(self) -> str:
        """Convenience property for primary author."""
        return self.metadata.author
    
    @property
    def series(self) -> Optional[str]:
        """Convenience property for series name."""
        return self.metadata.series
    
    @property
    def asin(self) -> Optional[str]:
        """Convenience property for ASIN."""
        return self.metadata.asin
    
    @property
    def isbn(self) -> Optional[str]:
        """Convenience property for ISBN."""
        return self.metadata.isbn
    
    @property
    def file_exists(self) -> bool:
        """Check if the book file exists on disk."""
        return self.file_path is not None and self.file_path.exists()
    
    @property
    def file_size_human(self) -> str:
        """Human-readable file size."""
        if not self.file_path or not self.file_path.exists():
            return "Unknown"
        
        size = self.file_path.stat().st_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def update_status(self, status: BookStatus, error_message: Optional[str] = None):
        """Update book processing status."""
        self.status = status
        self.error_message = error_message
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert book to dictionary for serialization."""
        return {
            'metadata': self.metadata.dict(),
            'file_path': str(self.file_path) if self.file_path else None,
            'calibre_id': self.calibre_id,
            'status': self.status.value,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Book':
        """Create book instance from dictionary."""
        metadata = BookMetadata(**data['metadata'])
        
        book = cls(
            metadata=metadata,
            file_path=Path(data['file_path']) if data['file_path'] else None,
            calibre_id=data.get('calibre_id'),
            status=BookStatus(data['status']),
            error_message=data.get('error_message'),
        )
        
        # Parse timestamps
        if 'created_at' in data:
            book.created_at = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            book.updated_at = datetime.fromisoformat(data['updated_at'])
        
        return book


@dataclass
class DownloadResult:
    """Result of a book download operation."""
    book: Book
    success: bool
    error: Optional[str] = None
    download_time: Optional[float] = None
    file_size: Optional[int] = None


@dataclass
class ConversionResult:
    """Result of a book format conversion operation."""
    input_file: Path
    output_file: Optional[Path]
    input_format: BookFormat
    output_format: BookFormat
    success: bool
    error: Optional[str] = None
    conversion_time: Optional[float] = None
    file_size_before: Optional[int] = None
    file_size_after: Optional[int] = None


@dataclass
class ASINLookupResult:
    """Result of an ASIN lookup operation."""
    query_title: str
    query_author: Optional[str]
    asin: Optional[str]
    metadata: Optional[Dict[str, Any]]
    source: Optional[str]
    success: bool
    error: Optional[str] = None
    lookup_time: Optional[float] = None
    from_cache: bool = False


class LibraryStats(BaseModel):
    """Statistics about a Calibre library."""
    total_books: int = 0
    total_authors: int = 0
    total_series: int = 0
    library_size: int = 0  # in bytes
    last_updated: datetime = Field(default_factory=datetime.now)
    format_distribution: Dict[str, int] = Field(default_factory=dict)
    top_authors: List[tuple[str, int]] = Field(default_factory=list)
    books_without_asin: int = 0
    duplicate_titles: int = 0
    missing_covers: int = 0
    corrupted_files: int = 0
    
    @property
    def library_size_human(self) -> str:
        """Human-readable library size."""
        size = self.library_size
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    @property
    def books_without_asin_percent(self) -> float:
        """Percentage of books without ASIN."""
        if self.total_books == 0:
            return 0.0
        return (self.books_without_asin / self.total_books) * 100