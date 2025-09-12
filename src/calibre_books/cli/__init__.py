"""
CLI package for Calibre Books tool.

This package contains all command-line interface components including the main
dispatcher and individual command modules.

The CLI can be executed with: python -m calibre_books.cli
"""

from .main import main

__all__ = ["main"]
