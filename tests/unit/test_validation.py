"""
Unit tests for validation utilities.
"""

from calibre_books.utils.validation import (
    validate_asin,
    validate_isbn,
    validate_file_path,
    validate_url,
    validate_book_format,
    sanitize_filename,
)


class TestASINValidation:
    """Test ASIN validation functionality."""

    def test_valid_asin(self):
        """Test valid ASIN formats."""
        valid_asins = [
            "B00ZVA3XL6",
            "B01234567X",
            "1234567890",
            "ABCDEFGHIJ",
        ]

        for asin in valid_asins:
            assert validate_asin(asin), f"ASIN {asin} should be valid"

    def test_invalid_asin(self):
        """Test invalid ASIN formats."""
        invalid_asins = [
            "",
            "B00ZVA3XL",  # Too short
            "B00ZVA3XL67",  # Too long
            "B00ZVA3XL!",  # Invalid character
            None,
            123,
        ]

        for asin in invalid_asins:
            assert not validate_asin(asin), f"ASIN {asin} should be invalid"

    def test_case_insensitive_asin(self):
        """Test that ASINs are case-insensitive."""
        assert validate_asin("b00zva3xl6"), "Lowercase ASIN should be valid"
        assert validate_asin("B00ZVA3XL6"), "Uppercase ASIN should be valid"
        assert validate_asin("b00ZvA3xL6"), "Mixed case ASIN should be valid"


class TestISBNValidation:
    """Test ISBN validation functionality."""

    def test_valid_isbn10(self):
        """Test valid ISBN-10 formats."""
        valid_isbns = [
            "0486419738",  # Real ISBN-10 with valid checksum
            "020161622X",  # Real ISBN-10 ending with X
            "0-486-41973-8",  # With dashes
            "0 486 41973 8",  # With spaces
        ]

        for isbn in valid_isbns:
            is_valid, normalized = validate_isbn(isbn)
            assert is_valid, f"ISBN-10 {isbn} should be valid"
            assert normalized is not None

    def test_valid_isbn13(self):
        """Test valid ISBN-13 formats."""
        valid_isbns = [
            "9780486419732",  # Real ISBN-13 with valid checksum
            "978-0-486-41973-2",  # With dashes
            "978 0 486 41973 2",  # With spaces
        ]

        for isbn in valid_isbns:
            is_valid, normalized = validate_isbn(isbn)
            assert is_valid, f"ISBN-13 {isbn} should be valid"
            assert normalized is not None

    def test_invalid_isbn(self):
        """Test invalid ISBN formats."""
        invalid_isbns = [
            "",
            "01234",  # Too short
            "01234567890123",  # Too long
            "invalid",  # Not numeric
            None,
        ]

        for isbn in invalid_isbns:
            is_valid, normalized = validate_isbn(isbn)
            assert not is_valid, f"ISBN {isbn} should be invalid"
            assert normalized is None


class TestFilePathValidation:
    """Test file path validation functionality."""

    def test_valid_path(self):
        """Test valid file paths."""
        is_valid, path, error = validate_file_path("/tmp/test.txt")
        assert is_valid
        assert path is not None
        assert error is None

    def test_invalid_path(self):
        """Test invalid file paths."""
        is_valid, path, error = validate_file_path("")
        assert not is_valid
        assert path is None
        assert error is not None

    def test_path_expansion(self):
        """Test path expansion (~, relative paths)."""
        is_valid, path, error = validate_file_path("~/test.txt")
        assert is_valid
        assert path is not None
        assert str(path).startswith("/")  # Should be absolute


class TestURLValidation:
    """Test URL validation functionality."""

    def test_valid_urls(self):
        """Test valid URLs."""
        valid_urls = [
            "http://example.com",
            "https://example.com/path",
            "https://example.com/path?query=value",
        ]

        for url in valid_urls:
            is_valid, error = validate_url(url)
            assert is_valid, f"URL {url} should be valid"
            assert error is None

    def test_invalid_urls(self):
        """Test invalid URLs."""
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com",  # Wrong scheme
            "http://",  # Missing hostname
        ]

        for url in invalid_urls:
            is_valid, error = validate_url(url)
            assert not is_valid, f"URL {url} should be invalid"
            assert error is not None


class TestBookFormatValidation:
    """Test book format validation."""

    def test_valid_formats(self):
        """Test valid book formats."""
        valid_formats = [
            "mobi",
            "MOBI",
            ".mobi",
            "epub",
            "EPUB",
            ".epub",
            "pdf",
            "PDF",
            ".pdf",
        ]

        for fmt in valid_formats:
            is_valid, normalized = validate_book_format(fmt)
            assert is_valid, f"Format {fmt} should be valid"
            assert normalized in ["mobi", "epub", "pdf"]

    def test_invalid_formats(self):
        """Test invalid book formats."""
        invalid_formats = [
            "",
            "invalid",
            "doc",  # Not supported
            None,
        ]

        for fmt in invalid_formats:
            is_valid, normalized = validate_book_format(fmt)
            assert not is_valid, f"Format {fmt} should be invalid"
            assert normalized is None


class TestFilenameSanitization:
    """Test filename sanitization."""

    def test_sanitize_valid_filename(self):
        """Test sanitizing valid filenames."""
        filename = "My Book Title.epub"
        sanitized = sanitize_filename(filename)
        assert sanitized == filename

    def test_sanitize_invalid_characters(self):
        """Test sanitizing filenames with invalid characters."""
        filename = 'My<Book>Title:"With|Invalid?Chars*.epub'
        sanitized = sanitize_filename(filename)
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert '"' not in sanitized
        assert "|" not in sanitized
        assert "?" not in sanitized
        assert "*" not in sanitized
        assert sanitized.endswith(".epub")

    def test_sanitize_empty_filename(self):
        """Test sanitizing empty filename."""
        sanitized = sanitize_filename("")
        assert sanitized == "unnamed"

    def test_sanitize_long_filename(self):
        """Test sanitizing very long filename."""
        long_filename = "a" * 300 + ".epub"
        sanitized = sanitize_filename(long_filename, max_length=255)
        assert len(sanitized) <= 255
        assert sanitized.endswith(".epub")
