"""
Test Helper Utilities for Book Pipeline Path Resolution.

This module provides utility functions to resolve book pipeline paths
for test scripts, supporting CLI arguments, environment variables,
and fallback defaults for better test portability.
"""

import os
import argparse
from pathlib import Path
from typing import Optional


def get_test_book_path(
    cli_args: Optional[argparse.Namespace] = None,
    env_var: str = "CALIBRE_BOOKS_TEST_PATH",
    default_path: str = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline",
    validate_exists: bool = True,
) -> Path:
    """
    Resolve test book directory path from CLI args, environment, or default.

    Priority order:
    1. CLI arguments (if provided via cli_args.book_path)
    2. Environment Variable (CALIBRE_BOOKS_TEST_PATH by default)
    3. Default hardcoded path (for backward compatibility)

    Args:
        cli_args: Parsed CLI arguments namespace (optional)
        env_var: Environment variable name to check
        default_path: Fallback path if no other source is available
        validate_exists: Whether to validate that the path exists

    Returns:
        Path: Resolved book directory path as a Path object

    Raises:
        FileNotFoundError: If validate_exists=True and path doesn't exist
        ValueError: If resolved path is empty or invalid
    """
    resolved_path = None
    source = "default"

    # Priority 1: CLI arguments
    if cli_args and hasattr(cli_args, "book_path") and cli_args.book_path:
        resolved_path = cli_args.book_path
        source = "CLI argument"

    # Priority 2: Environment variable
    elif env_var in os.environ and os.environ[env_var].strip():
        resolved_path = os.environ[env_var].strip()
        source = f"environment variable {env_var}"

    # Priority 3: Default fallback
    else:
        resolved_path = default_path
        source = "default fallback"

    # Validate resolved path
    if not resolved_path or not resolved_path.strip():
        raise ValueError("Resolved book path is empty or invalid")

    # Convert to Path object
    book_path = Path(resolved_path).expanduser().resolve()

    # Optional existence validation
    if validate_exists and not book_path.exists():
        raise FileNotFoundError(
            f"Book directory not found (from {source}): {book_path}\n"
            f"Please ensure the directory exists or provide a valid path via:\n"
            f"  - CLI argument: --book-path /path/to/books\n"
            f"  - Environment: export {env_var}=/path/to/books"
        )

    return book_path


def add_book_path_argument(
    parser: argparse.ArgumentParser,
    dest: str = "book_path",
    help_text: Optional[str] = None,
    env_var: str = "CALIBRE_BOOKS_TEST_PATH",
    default_display: str = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline",
) -> None:
    """
    Add standardized book path argument to an ArgumentParser.

    This function adds a consistent --book-path argument with standard
    help text and environment variable reference to any argparse parser.

    Args:
        parser: The ArgumentParser instance to add the argument to
        dest: Destination attribute name in parsed args (default: book_path)
        help_text: Custom help text (uses standard text if None)
        env_var: Environment variable name to mention in help
        default_display: Default path to show in help text
    """
    if help_text is None:
        help_text = (
            f"Path to book directory for testing. "
            f"Can also be set via {env_var} environment variable. "
            f"Default: {default_display}"
        )

    parser.add_argument(
        "--book-path", dest=dest, type=str, metavar="PATH", help=help_text
    )


def get_single_book_path(
    book_dir: Path,
    relative_path: str = "single-book-test/sanderson_elantris.epub",
    validate_exists: bool = True,
) -> Path:
    """
    Resolve path to a single test book file within the book directory.

    This is a helper for tests that need to work with specific test files,
    allowing the base directory to be parameterized while maintaining
    the relative structure.

    Args:
        book_dir: Base book directory (from get_test_book_path)
        relative_path: Relative path to the specific test file
        validate_exists: Whether to validate that the file exists

    Returns:
        Path: Full path to the single book file

    Raises:
        FileNotFoundError: If validate_exists=True and file doesn't exist
    """
    single_book_path = book_dir / relative_path

    if validate_exists and not single_book_path.exists():
        raise FileNotFoundError(
            f"Test book file not found: {single_book_path}\n"
            f"Expected relative to book directory: {relative_path}"
        )

    return single_book_path


# Backward compatibility aliases
resolve_test_book_path = get_test_book_path  # Alternative name
add_book_path_arg = add_book_path_argument  # Shorter name
