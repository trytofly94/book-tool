#!/usr/bin/env python3
"""
Entry point for running the CLI package as a module.

This module resolves the RuntimeWarning that occurs when running:
    python -m calibre_books.cli.main

Instead, users can now run:
    python -m calibre_books.cli

This provides a cleaner module execution pattern and eliminates the
"found in sys.modules after import" warning.
"""

from .main import cli_entry_point


def main() -> None:
    """Main entry point for CLI module execution."""
    cli_entry_point()


if __name__ == "__main__":
    main()
