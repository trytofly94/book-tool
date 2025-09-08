"""
Unit tests for book data models.
"""

import pytest
from pathlib import Path

from calibre_books.core.book import (
    BookFormat,
    BookStatus,
    BookMetadata,
    Book,
)


class TestBookMetadata:
    """Test BookMetadata validation and functionality."""

    def test_minimal_valid_book(self):
        """Test creation of minimal valid book metadata."""
        book = BookMetadata(title="Test Book", author="Test Author")

        assert book.title == "Test Book"
        assert book.author == "Test Author"
        assert book.authors == ["Test Author"]  # Should be auto-populated
        assert book.language == "en"  # default value
        assert book.tags == []  # default empty list

    def test_book_with_authors_list(self):
        """Test book with multiple authors."""
        book = BookMetadata(
            title="Test Book",
            author="First Author",
            authors=["First Author", "Second Author"],
        )

        assert book.author == "First Author"
        assert book.authors == ["First Author", "Second Author"]

    def test_author_added_to_authors_list(self):
        """Test that primary author is added to authors list if not present."""
        book = BookMetadata(
            title="Test Book", author="Primary Author", authors=["Other Author"]
        )

        assert book.authors == ["Primary Author", "Other Author"]

    def test_asin_validation(self):
        """Test ASIN validation."""
        # Valid ASIN
        book = BookMetadata(title="Test Book", author="Test Author", asin="B00ZVA3XL6")
        assert book.asin == "B00ZVA3XL6"

        # Invalid ASIN should raise error
        with pytest.raises(ValueError, match="Invalid ASIN format"):
            BookMetadata(title="Test Book", author="Test Author", asin="invalid")

    def test_isbn_validation(self):
        """Test ISBN validation and normalization."""
        # Valid ISBN-10
        book = BookMetadata(title="Test Book", author="Test Author", isbn="0486419738")
        assert book.isbn == "0486419738"

        # Valid ISBN-13
        book = BookMetadata(
            title="Test Book", author="Test Author", isbn="9780486419732"
        )
        assert book.isbn == "9780486419732"

        # Invalid ISBN should raise error
        with pytest.raises(ValueError, match="Invalid ISBN format"):
            BookMetadata(title="Test Book", author="Test Author", isbn="invalid")

    def test_rating_validation(self):
        """Test rating field validation."""
        # Valid rating
        book = BookMetadata(title="Test Book", author="Test Author", rating=4)
        assert book.rating == 4

        # Invalid rating (too high) should raise error
        with pytest.raises(ValueError):
            BookMetadata(title="Test Book", author="Test Author", rating=6)

        # Invalid rating (too low) should raise error
        with pytest.raises(ValueError):
            BookMetadata(title="Test Book", author="Test Author", rating=0)

    def test_book_format_enum(self):
        """Test BookFormat enum usage."""
        book = BookMetadata(
            title="Test Book", author="Test Author", format=BookFormat.EPUB
        )

        assert book.format == BookFormat.EPUB
        assert book.format.value == "epub"


class TestBookClass:
    """Test the main Book dataclass."""

    def test_book_creation(self):
        """Test basic Book creation."""
        metadata = BookMetadata(title="Test", author="Author")
        book = Book(
            metadata=metadata,
            file_path=Path("/test/book.epub"),
            status=BookStatus.DOWNLOADED,
            calibre_id=1,
        )

        assert book.calibre_id == 1
        assert book.metadata.title == "Test"
        assert book.file_path == Path("/test/book.epub")
        assert book.status == BookStatus.DOWNLOADED

    def test_book_properties(self):
        """Test Book convenience properties."""
        metadata = BookMetadata(title="Test Book", author="Test Author")
        book = Book(
            metadata=metadata,
            file_path=Path("/test/book.epub"),
            status=BookStatus.DOWNLOADED,
        )

        # Test convenience properties
        assert book.title == "Test Book"
        assert book.author == "Test Author"


class TestEnums:
    """Test enum classes."""

    def test_book_format_enum(self):
        """Test BookFormat enum values."""
        assert BookFormat.MOBI.value == "mobi"
        assert BookFormat.EPUB.value == "epub"
        assert BookFormat.PDF.value == "pdf"
        assert BookFormat.KFX.value == "kfx"

    def test_book_status_enum(self):
        """Test BookStatus enum values."""
        assert BookStatus.PENDING.value == "pending"
        assert BookStatus.DOWNLOADING.value == "downloading"
        assert BookStatus.DOWNLOADED.value == "downloaded"
        assert BookStatus.CONVERTING.value == "converting"
        assert BookStatus.CONVERTED.value == "converted"
        assert BookStatus.FAILED.value == "failed"
        assert BookStatus.COMPLETED.value == "completed"
