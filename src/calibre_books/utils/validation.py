"""
Input validation utilities for Calibre Books CLI.

This module provides validation functions for various input types including
ASINs, file paths, URLs, and other common data formats.
"""

import re
import subprocess
import zipfile
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from urllib.parse import urlparse
from enum import Enum


def validate_asin(asin: str) -> bool:
    """
    Validate Amazon ASIN format.

    ASINs are 10-character alphanumeric identifiers used by Amazon.
    They can contain uppercase letters A-Z and digits 0-9.

    Args:
        asin: ASIN string to validate

    Returns:
        True if valid ASIN format, False otherwise
    """
    if not asin or not isinstance(asin, str):
        return False

    # ASIN pattern: exactly 10 characters, alphanumeric
    asin_pattern = re.compile(r"^[A-Z0-9]{10}$")
    return bool(asin_pattern.match(asin.upper()))


def validate_isbn(isbn: str) -> Tuple[bool, Optional[str]]:
    """
    Validate and normalize ISBN (10 or 13 digit).

    Args:
        isbn: ISBN string to validate

    Returns:
        Tuple of (is_valid, normalized_isbn)
    """
    if not isbn or not isinstance(isbn, str):
        return False, None

    # Remove hyphens, spaces, and convert to uppercase
    clean_isbn = re.sub(r"[-\s]", "", isbn.upper())

    # Check ISBN-10
    if len(clean_isbn) == 10:
        if re.match(r"^[0-9]{9}[0-9X]$", clean_isbn):
            # Validate checksum
            if _validate_isbn10_checksum(clean_isbn):
                return True, clean_isbn

    # Check ISBN-13
    elif len(clean_isbn) == 13:
        if re.match(r"^[0-9]{13}$", clean_isbn):
            # Validate checksum
            if _validate_isbn13_checksum(clean_isbn):
                return True, clean_isbn

    return False, None


def _validate_isbn10_checksum(isbn: str) -> bool:
    """Validate ISBN-10 checksum."""
    checksum = 0
    for i, char in enumerate(isbn[:-1]):
        checksum += (10 - i) * int(char)

    check_digit = isbn[-1]
    if check_digit == "X":
        checksum += 10
    else:
        checksum += int(check_digit)

    return checksum % 11 == 0


def _validate_isbn13_checksum(isbn: str) -> bool:
    """Validate ISBN-13 checksum."""
    checksum = 0
    for i, char in enumerate(isbn[:-1]):
        weight = 1 if i % 2 == 0 else 3
        checksum += weight * int(char)

    check_digit = int(isbn[-1])
    return (10 - (checksum % 10)) % 10 == check_digit


def validate_file_path(
    path: str,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
    create_parents: bool = False,
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Validate file path and optionally check existence.

    Args:
        path: Path string to validate
        must_exist: Whether path must already exist
        must_be_file: Whether path must be a file (if it exists)
        must_be_dir: Whether path must be a directory (if it exists)
        create_parents: Whether to create parent directories

    Returns:
        Tuple of (is_valid, resolved_path, error_message)
    """
    if not path or not isinstance(path, str):
        return False, None, "Path is empty or invalid"

    try:
        path_obj = Path(path).expanduser().resolve()

        # Check existence requirements
        if must_exist and not path_obj.exists():
            return False, path_obj, f"Path does not exist: {path_obj}"

        # Check type requirements
        if path_obj.exists():
            if must_be_file and not path_obj.is_file():
                return False, path_obj, f"Path is not a file: {path_obj}"
            if must_be_dir and not path_obj.is_dir():
                return False, path_obj, f"Path is not a directory: {path_obj}"

        # Create parent directories if requested
        if create_parents and not path_obj.parent.exists():
            try:
                path_obj.parent.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return False, path_obj, f"Cannot create parent directories: {e}"

        return True, path_obj, None

    except (OSError, ValueError) as e:
        return False, None, f"Invalid path: {e}"


def validate_url(
    url: str, allowed_schemes: Optional[List[str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate URL format and scheme.

    Args:
        url: URL string to validate
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url or not isinstance(url, str):
        return False, "URL is empty or invalid"

    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]

    try:
        parsed = urlparse(url)

        # Check if scheme is present and allowed
        if not parsed.scheme:
            return False, "URL missing scheme (http/https)"

        if parsed.scheme.lower() not in allowed_schemes:
            return (
                False,
                f"URL scheme '{parsed.scheme}' not in allowed schemes: {allowed_schemes}",
            )

        # Check if hostname is present
        if not parsed.netloc:
            return False, "URL missing hostname"

        return True, None

    except Exception as e:
        return False, f"Invalid URL format: {e}"


def validate_book_format(format_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate book format name.

    Args:
        format_name: Format name to validate (e.g., 'mobi', 'epub')

    Returns:
        Tuple of (is_valid, normalized_format)
    """
    if not format_name or not isinstance(format_name, str):
        return False, None

    # Supported formats (normalize to lowercase)
    supported_formats = {
        "mobi",
        "epub",
        "pdf",
        "azw",
        "azw3",
        "azw4",
        "kfx",
        "txt",
        "rtf",
        "html",
        "docx",
        "odt",
        "fb2",
        "lit",
        "pdb",
        "rb",
        "tcr",
        "pml",
    }

    normalized = format_name.lower().strip()

    # Remove leading dot if present
    if normalized.startswith("."):
        normalized = normalized[1:]

    if normalized in supported_formats:
        return True, normalized
    else:
        return False, None


def validate_series_number(series_number: str) -> Tuple[bool, Optional[float]]:
    """
    Validate series number (can be integer or decimal).

    Args:
        series_number: Series number string to validate

    Returns:
        Tuple of (is_valid, parsed_number)
    """
    if not series_number or not isinstance(series_number, str):
        return False, None

    try:
        # Try to parse as float (handles both integers and decimals)
        number = float(series_number.strip())

        # Series numbers should be positive
        if number <= 0:
            return False, None

        return True, number

    except (ValueError, TypeError):
        return False, None


def validate_rating(rating: str) -> Tuple[bool, Optional[int]]:
    """
    Validate book rating (typically 1-5 stars).

    Args:
        rating: Rating string to validate

    Returns:
        Tuple of (is_valid, parsed_rating)
    """
    if not rating or not isinstance(rating, str):
        return False, None

    try:
        rating_int = int(rating.strip())

        # Rating should be between 1 and 5
        if 1 <= rating_int <= 5:
            return True, rating_int
        else:
            return False, None

    except (ValueError, TypeError):
        return False, None


def validate_config_section(section_name: str) -> bool:
    """
    Validate configuration section name.

    Args:
        section_name: Configuration section name to validate

    Returns:
        True if valid section name, False otherwise
    """
    if not section_name or not isinstance(section_name, str):
        return False

    valid_sections = {"download", "calibre", "asin_lookup", "conversion", "logging"}

    return section_name.lower() in valid_sections


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename by removing/replacing invalid characters.

    Args:
        filename: Original filename
        max_length: Maximum filename length

    Returns:
        Sanitized filename
    """
    if not filename or not isinstance(filename, str):
        return "unnamed"

    # Remove or replace invalid filename characters
    invalid_chars = r'<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)

    # Trim whitespace and dots (Windows doesn't allow filenames ending with dots)
    filename = filename.strip().rstrip(".")

    # Ensure filename isn't empty
    if not filename:
        filename = "unnamed"

    # Truncate if too long, but preserve extension if present
    if len(filename) > max_length:
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            max_name_length = max_length - len(ext) - 1
            filename = name[:max_name_length] + "." + ext
        else:
            filename = filename[:max_length]

    return filename


class ValidationStatus(Enum):
    """File validation status codes."""

    VALID = "valid"
    INVALID = "invalid"
    CORRUPTED = "corrupted"
    EXTENSION_MISMATCH = "extension_mismatch"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNREADABLE = "unreadable"


class ValidationResult:
    """
    Result of file validation.

    Attributes:
        status: ValidationStatus indicating the result
        file_path: Path to the validated file
        format_detected: Detected file format (None if unknown)
        format_expected: Expected format based on extension
        errors: List of error messages
        warnings: List of warning messages
        details: Additional validation details
    """

    def __init__(
        self,
        status: ValidationStatus,
        file_path: Path,
        format_detected: Optional[str] = None,
        format_expected: Optional[str] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.status = status
        self.file_path = file_path
        self.format_detected = format_detected
        self.format_expected = format_expected
        self.errors = errors or []
        self.warnings = warnings or []
        self.details = details or {}

    @property
    def is_valid(self) -> bool:
        """Return True if file is valid."""
        return self.status == ValidationStatus.VALID

    @property
    def has_extension_mismatch(self) -> bool:
        """Return True if there's an extension/content mismatch."""
        return self.status == ValidationStatus.EXTENSION_MISMATCH

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def add_detail(self, key: str, value: Any) -> None:
        """Add a validation detail."""
        self.details[key] = value

    def __str__(self) -> str:
        """String representation of validation result."""
        status_emoji = {
            ValidationStatus.VALID: "✓",
            ValidationStatus.INVALID: "✗",
            ValidationStatus.CORRUPTED: "⚠",
            ValidationStatus.EXTENSION_MISMATCH: "⚠",
            ValidationStatus.UNSUPPORTED_FORMAT: "?",
            ValidationStatus.UNREADABLE: "✗",
        }

        emoji = status_emoji.get(self.status, "?")
        return f"{emoji} {self.file_path.name} ({self.status.value})"


def detect_file_format(file_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Detect actual file format using magic bytes and file command.

    Args:
        file_path: Path to file to analyze

    Returns:
        Tuple of (detected_format, mime_type) or (None, None) if detection fails
    """
    try:
        # First try using Python's built-in magic number detection
        magic_format = _detect_format_by_magic_bytes(file_path)
        if magic_format:
            return magic_format, None

        # Fall back to system 'file' command if available
        try:
            # Try with --mime-type first
            result = subprocess.run(
                ["file", "--mime-type", "--brief", str(file_path)],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                mime_type = result.stdout.strip()
                format_name = _mime_to_format(mime_type)
                if format_name:
                    return format_name, mime_type

            # Try without --mime-type to get descriptive output
            result = subprocess.run(
                ["file", "--brief", str(file_path)],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                description = result.stdout.strip().lower()
                if "mobipocket" in description:
                    return "mobi", description
                elif "epub" in description:
                    return "epub", description
                elif "pdf" in description:
                    return "pdf", description

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None, None

    except Exception:
        return None, None


def _detect_format_by_magic_bytes(file_path: Path) -> Optional[str]:
    """Detect file format using magic bytes."""
    try:
        with open(file_path, "rb") as f:
            # Read first 100 bytes to capture MOBI signatures at offset 60
            header = f.read(100)

        if not header:
            return None

        # EPUB (ZIP file starting with specific structure)
        if header.startswith(b"PK\x03\x04"):
            # Check if it's actually an EPUB by looking for mimetype file
            try:
                with zipfile.ZipFile(file_path, "r") as zf:
                    if "mimetype" in zf.namelist():
                        mimetype = zf.read("mimetype").decode("utf-8").strip()
                        if mimetype == "application/epub+zip":
                            return "epub"
                # If it's a ZIP but not EPUB, it might be corrupted EPUB
                return "zip"
            except zipfile.BadZipFile:
                return "corrupted_zip"

        # MOBI files (check for signature at offset 60)
        if len(header) >= 68:
            mobi_signature = header[60:68]
            if mobi_signature == b"BOOKMOBI":
                return "mobi"
            elif mobi_signature == b"TPZ3\x00\x00\x00\x00":
                return "azw3"

        # Alternative MOBI/AZW detection for other signatures
        if b"TPZ" in header[:100]:
            return "azw"

        # PDF files
        if header.startswith(b"%PDF"):
            return "pdf"

        # Microsoft Office documents (including Word docs misnamed as EPUB)
        if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            return "ms_office"

        # Office Open XML (modern Word docs)
        if header.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(file_path, "r") as zf:
                    if "[Content_Types].xml" in zf.namelist():
                        # This is an Office document
                        if "word/" in str(zf.namelist()):
                            return "docx"
                        elif "xl/" in str(zf.namelist()):
                            return "xlsx"
                        elif "ppt/" in str(zf.namelist()):
                            return "pptx"
                        else:
                            return "office_document"
            except zipfile.BadZipFile:
                pass

        # Plain text
        try:
            header.decode("utf-8")
            # If it decodes as UTF-8, it might be text
            if all(
                32 <= ord(char) <= 126 or char in "\n\r\t"
                for char in header.decode("utf-8")
            ):
                return "txt"
        except UnicodeDecodeError:
            pass

        return None

    except (OSError, IOError):
        return None


def _mime_to_format(mime_type: str) -> Optional[str]:
    """Convert MIME type to format name."""
    mime_mapping = {
        "application/epub+zip": "epub",
        "application/x-mobipocket-ebook": "mobi",
        "application/pdf": "pdf",
        "text/plain": "txt",
        "application/zip": "zip",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/octet-stream": "binary",
    }

    # Handle special cases where file command gives specific descriptions
    if "mobipocket" in mime_type.lower():
        return "mobi"

    return mime_mapping.get(mime_type)


def check_extension_mismatch(
    file_path: Path,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if file extension matches actual content.

    Args:
        file_path: Path to file to check

    Returns:
        Tuple of (has_mismatch, expected_format, detected_format)
    """
    # Get expected format from extension
    suffix = file_path.suffix.lower()
    expected_format = suffix.lstrip(".") if suffix else None

    # Detect actual format
    detected_format, _ = detect_file_format(file_path)

    # Check for mismatch
    if not expected_format or not detected_format:
        return False, expected_format, detected_format

    # Some formats are compatible/related
    compatible_formats = {
        "epub": {"epub", "zip"},  # EPUB is a ZIP file
        "mobi": {"mobi", "azw", "azw3"},  # Related Amazon formats
        "azw": {"mobi", "azw", "azw3"},
        "azw3": {"mobi", "azw", "azw3"},
    }

    expected_set = compatible_formats.get(expected_format, {expected_format})
    has_mismatch = detected_format not in expected_set

    return has_mismatch, expected_format, detected_format


def validate_epub_structure(file_path: Path) -> ValidationResult:
    """
    Validate EPUB file structure and required components.

    Args:
        file_path: Path to EPUB file to validate

    Returns:
        ValidationResult with detailed validation information
    """
    result = ValidationResult(
        status=ValidationStatus.VALID, file_path=file_path, format_expected="epub"
    )

    try:
        # Check if it's a valid ZIP file first
        with zipfile.ZipFile(file_path, "r") as zf:
            namelist = zf.namelist()

            # Check for required mimetype file
            if "mimetype" not in namelist:
                result.status = ValidationStatus.INVALID
                result.add_error("Missing required 'mimetype' file")
            else:
                # Validate mimetype content
                try:
                    mimetype = zf.read("mimetype").decode("utf-8").strip()
                    if mimetype != "application/epub+zip":
                        result.status = ValidationStatus.INVALID
                        result.add_error(f"Invalid mimetype: {mimetype}")
                    result.add_detail("mimetype", mimetype)
                except Exception as e:
                    result.status = ValidationStatus.INVALID
                    result.add_error(f"Cannot read mimetype: {e}")

            # Check for META-INF/container.xml
            if "META-INF/container.xml" not in namelist:
                result.status = ValidationStatus.INVALID
                result.add_error("Missing required 'META-INF/container.xml'")
            else:
                result.add_detail("has_container_xml", True)

            # Check for at least one .opf file (package document)
            opf_files = [name for name in namelist if name.endswith(".opf")]
            if not opf_files:
                result.status = ValidationStatus.INVALID
                result.add_error("No OPF (package document) file found")
            else:
                result.add_detail("opf_files", opf_files)

            # Basic structure checks
            result.add_detail("total_files", len(namelist))
            result.add_detail(
                "has_images",
                any(
                    name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".svg"))
                    for name in namelist
                ),
            )
            result.add_detail(
                "has_css", any(name.lower().endswith(".css") for name in namelist)
            )
            result.add_detail(
                "has_html",
                any(name.lower().endswith((".html", ".xhtml")) for name in namelist),
            )

            # If we had errors, mark as detected format
            result.format_detected = (
                "epub" if result.status == ValidationStatus.VALID else "corrupted_epub"
            )

    except zipfile.BadZipFile:
        result.status = ValidationStatus.CORRUPTED
        result.add_error("File is not a valid ZIP archive")
        result.format_detected = "corrupted_zip"
    except Exception as e:
        result.status = ValidationStatus.UNREADABLE
        result.add_error(f"Cannot read file: {e}")

    return result


def validate_mobi_header(file_path: Path) -> ValidationResult:
    """
    Validate MOBI file header and basic structure.

    Args:
        file_path: Path to MOBI file to validate

    Returns:
        ValidationResult with detailed validation information
    """
    result = ValidationResult(
        status=ValidationStatus.VALID, file_path=file_path, format_expected="mobi"
    )

    try:
        with open(file_path, "rb") as f:
            # Read enough bytes to check MOBI header
            header = f.read(1024)

            if len(header) < 68:
                result.status = ValidationStatus.INVALID
                result.add_error("File too small to be a valid MOBI file")
                return result

            # Check for MOBI magic signatures
            # Standard MOBI signature at offset 60
            mobi_signature = header[60:68]

            if mobi_signature == b"BOOKMOBI":
                result.format_detected = "mobi"
                result.add_detail("mobi_type", "BOOKMOBI")
            elif mobi_signature == b"TPZ3":
                result.format_detected = "azw3"  # Kindle AZW3 format
                result.add_detail("mobi_type", "TPZ3")
            else:
                # Check for other Kindle signatures
                if b"TPZ" in header[:100]:
                    result.format_detected = "azw"
                    result.add_detail("mobi_type", "TPZ")
                else:
                    result.status = ValidationStatus.INVALID
                    result.add_error(
                        "Invalid MOBI signature - not a valid MOBI/AZW file"
                    )
                    return result

            # Extract basic header information
            try:
                # Read database name (bytes 0-31)
                db_name = header[:32].rstrip(b"\x00").decode("utf-8", errors="ignore")
                result.add_detail("database_name", db_name)

                # Read creation date (bytes 36-39)
                creation_date = int.from_bytes(header[36:40], byteorder="big")
                result.add_detail("creation_date", creation_date)

                # Read record count (bytes 76-77)
                if len(header) >= 78:
                    record_count = int.from_bytes(header[76:78], byteorder="big")
                    result.add_detail("record_count", record_count)

                    if record_count == 0:
                        result.add_warning("MOBI file has no records")

            except Exception as e:
                result.add_warning(f"Could not parse header details: {e}")

    except Exception as e:
        result.status = ValidationStatus.UNREADABLE
        result.add_error(f"Cannot read file: {e}")

    return result


def validate_file_format(file_path: Path) -> ValidationResult:
    """
    Comprehensive file format validation.

    Args:
        file_path: Path to file to validate

    Returns:
        ValidationResult with comprehensive validation information
    """
    # Basic file existence check
    if not file_path.exists():
        return ValidationResult(
            status=ValidationStatus.UNREADABLE,
            file_path=file_path,
            errors=["File does not exist"],
        )

    if not file_path.is_file():
        return ValidationResult(
            status=ValidationStatus.UNREADABLE,
            file_path=file_path,
            errors=["Path is not a regular file"],
        )

    # Check file size (empty files are invalid)
    try:
        file_size = file_path.stat().st_size
        if file_size == 0:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                file_path=file_path,
                errors=["File is empty"],
            )
    except OSError as e:
        return ValidationResult(
            status=ValidationStatus.UNREADABLE,
            file_path=file_path,
            errors=[f"Cannot read file stats: {e}"],
        )

    # Check extension mismatch
    has_mismatch, expected_format, detected_format = check_extension_mismatch(file_path)

    if has_mismatch:
        return ValidationResult(
            status=ValidationStatus.EXTENSION_MISMATCH,
            file_path=file_path,
            format_expected=expected_format,
            format_detected=detected_format,
            errors=[
                f"Extension mismatch: expected {expected_format}, detected {detected_format}"
            ],
        )

    # Format-specific validation
    if expected_format == "epub" or detected_format == "epub":
        return validate_epub_structure(file_path)
    elif expected_format in ["mobi", "azw", "azw3"] or detected_format in [
        "mobi",
        "azw",
        "azw3",
    ]:
        return validate_mobi_header(file_path)
    else:
        # Generic validation for other formats
        result = ValidationResult(
            status=ValidationStatus.VALID,
            file_path=file_path,
            format_expected=expected_format,
            format_detected=detected_format,
        )

        # Add basic file info
        result.add_detail("file_size", file_size)
        result.add_detail("readable", True)

        return result
