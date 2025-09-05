"""
Input validation utilities for Calibre Books CLI.

This module provides validation functions for various input types including
ASINs, file paths, URLs, and other common data formats.
"""

import re
from pathlib import Path
from typing import Optional, List, Tuple
from urllib.parse import urlparse


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
    asin_pattern = re.compile(r'^[A-Z0-9]{10}$')
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
    clean_isbn = re.sub(r'[-\s]', '', isbn.upper())
    
    # Check ISBN-10
    if len(clean_isbn) == 10:
        if re.match(r'^[0-9]{9}[0-9X]$', clean_isbn):
            # Validate checksum
            if _validate_isbn10_checksum(clean_isbn):
                return True, clean_isbn
    
    # Check ISBN-13
    elif len(clean_isbn) == 13:
        if re.match(r'^[0-9]{13}$', clean_isbn):
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
    if check_digit == 'X':
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


def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
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
        allowed_schemes = ['http', 'https']
    
    try:
        parsed = urlparse(url)
        
        # Check if scheme is present and allowed
        if not parsed.scheme:
            return False, "URL missing scheme (http/https)"
        
        if parsed.scheme.lower() not in allowed_schemes:
            return False, f"URL scheme '{parsed.scheme}' not in allowed schemes: {allowed_schemes}"
        
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
        'mobi', 'epub', 'pdf', 'azw', 'azw3', 'azw4', 'kfx',
        'txt', 'rtf', 'html', 'docx', 'odt', 'fb2', 'lit',
        'pdb', 'rb', 'tcr', 'pml'
    }
    
    normalized = format_name.lower().strip()
    
    # Remove leading dot if present
    if normalized.startswith('.'):
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
    
    valid_sections = {
        'download', 'calibre', 'asin_lookup', 'conversion', 'logging'
    }
    
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
        filename = filename.replace(char, '_')
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Trim whitespace and dots (Windows doesn't allow filenames ending with dots)
    filename = filename.strip().rstrip('.')
    
    # Ensure filename isn't empty
    if not filename:
        filename = "unnamed"
    
    # Truncate if too long, but preserve extension if present
    if len(filename) > max_length:
        if '.' in filename:
            name, ext = filename.rsplit('.', 1)
            max_name_length = max_length - len(ext) - 1
            filename = name[:max_name_length] + '.' + ext
        else:
            filename = filename[:max_length]
    
    return filename