"""
Utility functions package for Calibre Books CLI.

This package contains utility functions for logging setup, progress management,
input validation, and other common operations.
"""

from .logging import setup_logging, get_logger
from .progress import ProgressManager
from .validation import validate_asin, validate_file_path, validate_url
from .test_helpers import (
    get_test_book_path,
    add_book_path_argument,
    get_single_book_path,
    resolve_test_book_path,
    add_book_path_arg,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "ProgressManager",
    "validate_asin",
    "validate_file_path",
    "validate_url",
    "get_test_book_path",
    "add_book_path_argument",
    "get_single_book_path",
    "resolve_test_book_path",
    "add_book_path_arg",
]
