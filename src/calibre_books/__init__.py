"""
Calibre Books CLI Tool

A comprehensive command-line interface for book automation, including downloading,
ASIN lookup, Calibre integration, and format conversion.
"""

__version__ = "0.1.0"
__author__ = "Calibre Books CLI Team"
__email__ = "support@book-tool.com"
__description__ = "Professional CLI tool for book automation and Calibre integration"

# Package-level imports for convenience
from .core.book import Book
from .core.calibre import CalibreIntegration
from .config.manager import ConfigManager

__all__ = [
    "Book",
    "CalibreIntegration",
    "ConfigManager",
    "__version__",
]
