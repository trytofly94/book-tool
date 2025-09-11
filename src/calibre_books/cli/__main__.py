#!/usr/bin/env python3
"""
Module execution entry point for calibre_books.cli package.

This allows the CLI to be executed with: python -m calibre_books.cli

The __main__.py file provides a clean entry point that avoids the RuntimeWarning
that occurs when Python's -m flag tries to execute a module that's already been
imported through the package's __init__.py.
"""

from .main import cli_entry_point

if __name__ == "__main__":
    cli_entry_point()
