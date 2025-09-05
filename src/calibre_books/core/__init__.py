"""
Core business logic package for Calibre Books CLI.

This package contains all the core functionality including book models,
Calibre integration, download services, ASIN lookup, and format conversion.
"""

from .book import Book, BookMetadata, BookStatus
from .calibre import CalibreIntegration
from .downloader import BookDownloader
from .asin_lookup import ASINLookupService
from .converter import FormatConverter

__all__ = [
    "Book",
    "BookMetadata", 
    "BookStatus",
    "CalibreIntegration",
    "BookDownloader",
    "ASINLookupService",
    "FormatConverter",
]