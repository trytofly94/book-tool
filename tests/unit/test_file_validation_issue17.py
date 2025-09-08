"""
Unit tests for Issue #17 file validation system.

These tests cover the new file validation functionality added to detect
corrupted eBook files, extension mismatches, and specific format validation.
"""

import pytest
import tempfile
import zipfile
from pathlib import Path

from calibre_books.utils.validation import (
    detect_file_format,
    check_extension_mismatch,
    validate_epub_structure,
    validate_mobi_header,
    validate_file_format,
    ValidationStatus,
    ValidationResult,
)
from calibre_books.core.file_validator import FileValidator, ValidationCache


class TestFileFormatDetection:
    """Test file format detection using magic bytes."""

    def test_detect_epub_format(self):
        """Test detection of EPUB files (ZIP with mimetype)."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Create a basic EPUB structure
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("mimetype", "application/epub+zip")
                zf.writestr("META-INF/container.xml", "<container/>")
                zf.writestr("content.opf", "<package/>")

            format_detected, mime_type = detect_file_format(Path(tmp.name))
            assert format_detected == "epub"

    def test_detect_mobi_format(self):
        """Test detection of MOBI files using magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".mobi") as tmp:
            # Create a basic MOBI header with signature at offset 60
            header = b"\x00" * 60 + b"BOOKMOBI" + b"\x00" * 32
            Path(tmp.name).write_bytes(header)

            format_detected, mime_type = detect_file_format(Path(tmp.name))
            assert format_detected == "mobi"

    def test_detect_azw3_format(self):
        """Test detection of AZW3 files."""
        with tempfile.NamedTemporaryFile(suffix=".azw3") as tmp:
            # Create AZW3 header with TPZ3 signature
            header = b"\x00" * 60 + b"TPZ3\x00\x00\x00\x00" + b"\x00" * 24
            Path(tmp.name).write_bytes(header)

            format_detected, mime_type = detect_file_format(Path(tmp.name))
            assert format_detected == "azw3"

    def test_detect_pdf_format(self):
        """Test detection of PDF files."""
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            # PDF signature
            Path(tmp.name).write_bytes(b"%PDF-1.4\n")

            format_detected, mime_type = detect_file_format(Path(tmp.name))
            assert format_detected == "pdf"

    def test_detect_ms_office_format(self):
        """Test detection of MS Office documents (Word docs misnamed as EPUB)."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # MS Office compound document signature
            ms_office_signature = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
            Path(tmp.name).write_bytes(ms_office_signature + b"\x00" * 100)

            format_detected, mime_type = detect_file_format(Path(tmp.name))
            assert format_detected == "ms_office"

    def test_detect_docx_format(self):
        """Test detection of DOCX files (Office Open XML)."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Create a ZIP file that looks like a DOCX
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("[Content_Types].xml", "<Types/>")
                zf.writestr("word/document.xml", "<document/>")

            format_detected, mime_type = detect_file_format(Path(tmp.name))
            assert format_detected == "docx"

    def test_detect_corrupted_zip(self):
        """Test detection of corrupted ZIP files."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Write ZIP signature but corrupt the file
            Path(tmp.name).write_bytes(b"PK\x03\x04" + b"corrupted data")

            format_detected, mime_type = detect_file_format(Path(tmp.name))
            assert format_detected == "corrupted_zip"

    def test_detect_plain_zip(self):
        """Test detection of plain ZIP files (not EPUB)."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Create a plain ZIP without EPUB structure
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("file.txt", "content")

            format_detected, mime_type = detect_file_format(Path(tmp.name))
            assert format_detected == "zip"


class TestExtensionMismatchDetection:
    """Test extension mismatch detection."""

    def test_no_mismatch_epub(self):
        """Test that proper EPUB files have no mismatch."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Create valid EPUB
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("mimetype", "application/epub+zip")

            has_mismatch, expected, detected = check_extension_mismatch(Path(tmp.name))
            assert not has_mismatch
            assert expected == "epub"
            assert detected == "epub"

    def test_mismatch_word_doc_as_epub(self):
        """Test detection of Word document misnamed as EPUB."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # MS Word document signature
            ms_office_signature = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
            Path(tmp.name).write_bytes(ms_office_signature + b"\x00" * 100)

            has_mismatch, expected, detected = check_extension_mismatch(Path(tmp.name))
            assert has_mismatch
            assert expected == "epub"
            assert detected == "ms_office"

    def test_mismatch_docx_as_epub(self):
        """Test detection of DOCX document misnamed as EPUB."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Create DOCX structure
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("[Content_Types].xml", "<Types/>")
                zf.writestr("word/document.xml", "<document/>")

            has_mismatch, expected, detected = check_extension_mismatch(Path(tmp.name))
            assert has_mismatch
            assert expected == "epub"
            assert detected == "docx"

    def test_compatible_formats_no_mismatch(self):
        """Test that compatible formats don't trigger mismatch."""
        with tempfile.NamedTemporaryFile(suffix=".mobi") as tmp:
            # AZW3 in MOBI file (compatible)
            header = b"\x00" * 60 + b"TPZ3\x00\x00\x00\x00" + b"\x00" * 24
            Path(tmp.name).write_bytes(header)

            has_mismatch, expected, detected = check_extension_mismatch(Path(tmp.name))
            assert not has_mismatch  # AZW3 is compatible with MOBI
            assert expected == "mobi"
            assert detected == "azw3"


class TestEPUBValidation:
    """Test EPUB file structure validation."""

    def test_valid_epub_structure(self):
        """Test validation of proper EPUB structure."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("mimetype", "application/epub+zip")
                zf.writestr("META-INF/container.xml", "<container/>")
                zf.writestr("content.opf", "<package/>")
                zf.writestr("chapter1.html", "<html><body>Content</body></html>")
                zf.writestr("styles.css", "body { margin: 0; }")
                zf.writestr("cover.jpg", b"fake image data")

            result = validate_epub_structure(Path(tmp.name))
            assert result.is_valid
            assert result.status == ValidationStatus.VALID
            assert result.format_detected == "epub"
            assert result.details["has_container_xml"]
            assert result.details["has_html"]
            assert result.details["has_css"]
            assert result.details["has_images"]

    def test_epub_missing_mimetype(self):
        """Test EPUB missing required mimetype file."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("META-INF/container.xml", "<container/>")
                zf.writestr("content.opf", "<package/>")

            result = validate_epub_structure(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.INVALID
            assert "Missing required 'mimetype' file" in result.errors

    def test_epub_invalid_mimetype(self):
        """Test EPUB with invalid mimetype."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("mimetype", "application/zip")  # Wrong mimetype
                zf.writestr("META-INF/container.xml", "<container/>")
                zf.writestr("content.opf", "<package/>")

            result = validate_epub_structure(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.INVALID
            assert "Invalid mimetype" in result.errors[0]

    def test_epub_missing_container_xml(self):
        """Test EPUB missing META-INF/container.xml."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("mimetype", "application/epub+zip")
                zf.writestr("content.opf", "<package/>")

            result = validate_epub_structure(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.INVALID
            assert "Missing required 'META-INF/container.xml'" in result.errors

    def test_epub_missing_opf_file(self):
        """Test EPUB missing OPF package document."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("mimetype", "application/epub+zip")
                zf.writestr("META-INF/container.xml", "<container/>")

            result = validate_epub_structure(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.INVALID
            assert "No OPF (package document) file found" in result.errors

    def test_corrupted_epub_zip(self):
        """Test corrupted EPUB (bad ZIP file)."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Write corrupted ZIP data
            Path(tmp.name).write_bytes(b"PK\x03\x04corrupted")

            result = validate_epub_structure(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.CORRUPTED
            assert "File is not a valid ZIP archive" in result.errors
            assert result.format_detected == "corrupted_zip"


class TestMOBIValidation:
    """Test MOBI file header validation."""

    def test_valid_mobi_header(self):
        """Test validation of proper MOBI header."""
        with tempfile.NamedTemporaryFile(suffix=".mobi") as tmp:
            # Create basic MOBI header
            header = b"TestDatabase" + b"\x00" * 20  # Database name (32 bytes)
            header += b"\x00" * 4  # Attributes (4 bytes)
            header += b"\x12\x34\x56\x78"  # Creation date (4 bytes)
            header += b"\x00" * 20  # Various fields
            header += b"BOOKMOBI"  # MOBI signature at offset 60
            header += b"\x00" * 8  # More header data
            header += b"\x00\x05"  # Record count at offset 76 (5 records)
            header += b"\x00" * (1024 - len(header))  # Pad to 1KB

            Path(tmp.name).write_bytes(header)

            result = validate_mobi_header(Path(tmp.name))
            assert result.is_valid
            assert result.status == ValidationStatus.VALID
            assert result.format_detected == "mobi"
            assert result.details["mobi_type"] == "BOOKMOBI"
            assert "database_name" in result.details
            assert "creation_date" in result.details
            assert "record_count" in result.details

    def test_valid_azw3_header(self):
        """Test validation of AZW3 header."""
        with tempfile.NamedTemporaryFile(suffix=".azw3") as tmp:
            # Create AZW3 header with TPZ3 signature
            header = b"TestDatabase" + b"\x00" * 20  # Database name
            header += b"\x00" * 28  # Various fields to reach offset 60
            header += b"TPZ3" + b"\x00" * 4  # TPZ3 signature at offset 60
            header += b"\x00" * (1024 - len(header))  # Pad to 1KB

            Path(tmp.name).write_bytes(header)

            result = validate_mobi_header(Path(tmp.name))
            assert result.is_valid
            assert result.status == ValidationStatus.VALID
            assert result.format_detected == "azw3"
            assert result.details["mobi_type"] == "TPZ3"

    def test_invalid_mobi_signature(self):
        """Test MOBI file with invalid signature."""
        with tempfile.NamedTemporaryFile(suffix=".mobi") as tmp:
            # Create header with invalid signature
            header = b"TestDatabase" + b"\x00" * 20
            header += b"\x00" * 28
            header += b"BADMAGIC"  # Invalid signature
            header += b"\x00" * (1024 - len(header))

            Path(tmp.name).write_bytes(header)

            result = validate_mobi_header(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.INVALID
            assert "Invalid MOBI signature" in result.errors[0]

    def test_mobi_file_too_small(self):
        """Test MOBI file that's too small."""
        with tempfile.NamedTemporaryFile(suffix=".mobi") as tmp:
            # Write a file that's too small
            Path(tmp.name).write_bytes(b"tiny")

            result = validate_mobi_header(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.INVALID
            assert "File too small to be a valid MOBI file" in result.errors

    def test_mobi_zero_records_warning(self):
        """Test MOBI file with zero records (generates warning)."""
        with tempfile.NamedTemporaryFile(suffix=".mobi") as tmp:
            # Create MOBI with zero records
            header = b"TestDatabase" + b"\x00" * 20
            header += b"\x00" * 28
            header += b"BOOKMOBI" + b"\x00" * 8
            header += b"\x00\x00"  # Zero record count
            header += b"\x00" * (1024 - len(header))

            Path(tmp.name).write_bytes(header)

            result = validate_mobi_header(Path(tmp.name))
            assert result.is_valid  # Still valid, just has warning
            assert "MOBI file has no records" in result.warnings


class TestComprehensiveFileValidation:
    """Test comprehensive file format validation."""

    def test_nonexistent_file(self):
        """Test validation of non-existent file."""
        result = validate_file_format(Path("/nonexistent/file.epub"))
        assert not result.is_valid
        assert result.status == ValidationStatus.UNREADABLE
        assert "File does not exist" in result.errors

    def test_empty_file(self):
        """Test validation of empty file."""
        with tempfile.NamedTemporaryFile() as tmp:
            # File is empty by default
            result = validate_file_format(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.INVALID
            assert "File is empty" in result.errors

    def test_directory_instead_of_file(self):
        """Test validation when path points to directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_file_format(Path(tmpdir))
            assert not result.is_valid
            assert result.status == ValidationStatus.UNREADABLE
            assert "Path is not a regular file" in result.errors

    def test_extension_mismatch_triggers_mismatch_status(self):
        """Test that extension mismatch results in EXTENSION_MISMATCH status."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Write Word document content
            ms_signature = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
            Path(tmp.name).write_bytes(ms_signature + b"\x00" * 100)

            result = validate_file_format(Path(tmp.name))
            assert not result.is_valid
            assert result.status == ValidationStatus.EXTENSION_MISMATCH
            assert result.format_expected == "epub"
            assert result.format_detected == "ms_office"
            assert "Extension mismatch" in result.errors[0]

    def test_generic_format_validation(self):
        """Test validation of non-EPUB/MOBI formats."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            Path(tmp.name).write_text("Hello, World!")

            result = validate_file_format(Path(tmp.name))
            assert result.is_valid
            assert result.status == ValidationStatus.VALID
            assert result.format_expected == "txt"
            assert "file_size" in result.details
            assert result.details["readable"]


class TestFileValidator:
    """Test FileValidator class orchestration."""

    @pytest.fixture
    def validator(self):
        """Create FileValidator instance for testing."""
        return FileValidator(config={})

    def test_file_discovery(self, validator):
        """Test eBook file discovery in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "book1.epub").write_bytes(b"fake epub")
            (tmpdir_path / "book2.mobi").write_bytes(b"fake mobi")
            (tmpdir_path / "document.txt").write_bytes(b"text file")
            (tmpdir_path / "image.jpg").write_bytes(b"image")

            # Test discovery
            files = validator._discover_ebook_files(
                tmpdir_path, recursive=False, formats=None
            )
            ebook_names = [f.name for f in files]

            assert "book1.epub" in ebook_names
            assert "book2.mobi" in ebook_names
            assert "document.txt" in ebook_names  # TXT is supported
            assert "image.jpg" not in ebook_names  # JPG is not supported

    def test_format_filtering(self, validator):
        """Test file discovery with format filtering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test files
            (tmpdir_path / "book1.epub").write_bytes(b"fake epub")
            (tmpdir_path / "book2.mobi").write_bytes(b"fake mobi")
            (tmpdir_path / "book3.pdf").write_bytes(b"fake pdf")

            # Test filtering for EPUB only
            files = validator._discover_ebook_files(
                tmpdir_path, recursive=False, formats=["epub"]
            )
            assert len(files) == 1
            assert files[0].name == "book1.epub"

    def test_recursive_discovery(self, validator):
        """Test recursive file discovery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            subdir = tmpdir_path / "subdir"
            subdir.mkdir()

            # Create files in both directories
            (tmpdir_path / "book1.epub").write_bytes(b"fake epub")
            (subdir / "book2.mobi").write_bytes(b"fake mobi")

            # Test non-recursive
            files = validator._discover_ebook_files(
                tmpdir_path, recursive=False, formats=None
            )
            assert len(files) == 1

            # Test recursive
            files = validator._discover_ebook_files(
                tmpdir_path, recursive=True, formats=None
            )
            assert len(files) == 2

    def test_single_file_validation(self, validator):
        """Test validation of single file."""
        with tempfile.NamedTemporaryFile(suffix=".epub") as tmp:
            # Create valid EPUB
            with zipfile.ZipFile(tmp.name, "w") as zf:
                zf.writestr("mimetype", "application/epub+zip")
                zf.writestr("META-INF/container.xml", "<container/>")
                zf.writestr("content.opf", "<package/>")

            result = validator.validate_file(Path(tmp.name), use_cache=False)
            assert result.is_valid
            assert result.status == ValidationStatus.VALID

    def test_validation_summary_generation(self, validator):
        """Test generation of validation summary statistics."""
        # Create mock results
        results = [
            ValidationResult(
                ValidationStatus.VALID, Path("book1.epub"), format_detected="epub"
            ),
            ValidationResult(
                ValidationStatus.VALID, Path("book2.mobi"), format_detected="mobi"
            ),
            ValidationResult(
                ValidationStatus.EXTENSION_MISMATCH,
                Path("fake.epub"),
                format_expected="epub",
                format_detected="docx",
                errors=["Extension mismatch"],
            ),
            ValidationResult(
                ValidationStatus.CORRUPTED,
                Path("corrupt.mobi"),
                errors=["Corrupted file"],
            ),
        ]

        summary = validator.generate_summary(results)

        assert summary["total_files"] == 4
        assert summary["valid_files"] == 2
        assert summary["invalid_files"] == 2
        assert summary["extension_mismatches"] == 1
        assert summary["status_counts"]["valid"] == 2
        assert summary["status_counts"]["extension_mismatch"] == 1
        assert summary["status_counts"]["corrupted"] == 1
        assert summary["format_counts"]["epub"] == 1
        assert summary["format_counts"]["mobi"] == 1
        assert summary["format_counts"]["docx"] == 1
        assert len(summary["problem_files"]) == 2


class TestValidationCache:
    """Test validation caching functionality."""

    def test_cache_initialization(self):
        """Test cache initialization and file creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            cache = ValidationCache(cache_file)

            assert cache.cache_file == cache_file
            assert cache.cache_file.parent.exists()

    def test_cache_result_storage_and_retrieval(self):
        """Test storing and retrieving cached results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            cache = ValidationCache(cache_file)

            # Create a test file and result
            test_file = Path(tmpdir) / "test.epub"
            test_file.write_bytes(b"test content")

            original_result = ValidationResult(
                status=ValidationStatus.VALID,
                file_path=test_file,
                format_detected="epub",
                format_expected="epub",
                errors=[],
                warnings=["Test warning"],
                details={"test": "data"},
            )

            # Cache the result
            cache.cache_result(original_result)

            # Retrieve from cache
            cached_result = cache.get_cached_result(test_file)

            assert cached_result is not None
            assert cached_result.status == ValidationStatus.VALID
            assert cached_result.format_detected == "epub"
            assert cached_result.format_expected == "epub"
            assert cached_result.warnings == ["Test warning"]
            assert cached_result.details == {"test": "data"}

    def test_cache_invalidation_on_file_change(self):
        """Test that cache is invalidated when file changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            cache = ValidationCache(cache_file)

            # Create a test file
            test_file = Path(tmpdir) / "test.epub"
            test_file.write_bytes(b"original content")

            # Cache result for original file
            result = ValidationResult(ValidationStatus.VALID, test_file)
            cache.cache_result(result)

            # Verify cache hit
            cached_result = cache.get_cached_result(test_file)
            assert cached_result is not None

            # Modify file (changes mtime and size)
            test_file.write_bytes(b"modified content")

            # Cache should miss now
            cached_result = cache.get_cached_result(test_file)
            assert cached_result is None

    def test_cache_clear(self):
        """Test clearing the cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            cache = ValidationCache(cache_file)

            # Add some cached data
            test_file = Path(tmpdir) / "test.epub"
            test_file.write_bytes(b"test content")

            result = ValidationResult(ValidationStatus.VALID, test_file)
            cache.cache_result(result)

            # Verify data exists
            assert cache.get_cached_result(test_file) is not None
            assert cache_file.exists()

            # Clear cache
            cache.clear_cache()

            # Verify cache is empty
            assert cache.get_cached_result(test_file) is None
            assert not cache_file.exists()


class TestValidationResult:
    """Test ValidationResult class functionality."""

    def test_validation_result_creation(self):
        """Test creating validation results."""
        result = ValidationResult(
            status=ValidationStatus.VALID,
            file_path=Path("test.epub"),
            format_detected="epub",
            format_expected="epub",
        )

        assert result.is_valid
        assert not result.has_extension_mismatch
        assert result.errors == []
        assert result.warnings == []
        assert result.details == {}

    def test_validation_result_extension_mismatch(self):
        """Test extension mismatch detection in ValidationResult."""
        result = ValidationResult(
            status=ValidationStatus.EXTENSION_MISMATCH,
            file_path=Path("fake.epub"),
            format_detected="docx",
            format_expected="epub",
        )

        assert not result.is_valid
        assert result.has_extension_mismatch

    def test_validation_result_methods(self):
        """Test ValidationResult helper methods."""
        result = ValidationResult(ValidationStatus.INVALID, Path("test.epub"))

        # Test adding errors and warnings
        result.add_error("Test error")
        result.add_warning("Test warning")
        result.add_detail("key", "value")

        assert "Test error" in result.errors
        assert "Test warning" in result.warnings
        assert result.details["key"] == "value"

    def test_validation_result_string_representation(self):
        """Test string representation of validation results."""
        result = ValidationResult(ValidationStatus.VALID, Path("test.epub"))
        str_repr = str(result)

        assert "✓" in str_repr
        assert "test.epub" in str_repr
        assert "valid" in str_repr
