#!/usr/bin/env python3
"""
Unit tests for test_helpers module.

Tests the book path resolution functionality including CLI args,
environment variables, and fallback behavior.
"""

import os
import sys
import unittest
import tempfile
import argparse
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from calibre_books.utils.test_helpers import (  # noqa: E402
    get_test_book_path,
    add_book_path_argument,
    get_single_book_path,
)


class TestPathResolution(unittest.TestCase):
    """Test cases for book path resolution functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories for testing
        self.test_dir = tempfile.mkdtemp()
        self.test_book_dir = Path(self.test_dir) / "test_books"
        self.test_book_dir.mkdir()

        # Create a test book file
        self.test_book_file = (
            self.test_book_dir / "single-book-test" / "sanderson_elantris.epub"
        )
        self.test_book_file.parent.mkdir(parents=True)
        self.test_book_file.touch()

        # Store original environment to restore later
        self.original_env = os.environ.get("CALIBRE_BOOKS_TEST_PATH")

    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original environment
        if self.original_env:
            os.environ["CALIBRE_BOOKS_TEST_PATH"] = self.original_env
        elif "CALIBRE_BOOKS_TEST_PATH" in os.environ:
            del os.environ["CALIBRE_BOOKS_TEST_PATH"]

        # Clean up test directory
        import shutil

        shutil.rmtree(self.test_dir)

    def test_cli_args_priority(self):
        """Test that CLI args take highest priority."""
        # Create mock CLI args
        args = argparse.Namespace()
        args.book_path = str(self.test_book_dir)

        # Set environment variable (should be overridden)
        os.environ["CALIBRE_BOOKS_TEST_PATH"] = "/should/be/ignored"

        # Test path resolution
        result = get_test_book_path(cli_args=args)
        self.assertEqual(result.resolve(), self.test_book_dir.resolve())

    def test_environment_variable_priority(self):
        """Test that environment variable works when no CLI args."""
        # Set environment variable
        os.environ["CALIBRE_BOOKS_TEST_PATH"] = str(self.test_book_dir)

        # Test path resolution (no CLI args)
        result = get_test_book_path()
        self.assertEqual(result.resolve(), self.test_book_dir.resolve())

    def test_issue_46_dual_environment_variables(self):
        """Test Issue #46 dual environment variable support."""
        # Create two different test directories
        with (
            tempfile.TemporaryDirectory() as primary_dir,
            tempfile.TemporaryDirectory() as fallback_dir,
        ):
            primary_path = Path(primary_dir)
            fallback_path = Path(fallback_dir)

            # Test 1: Only BOOK_PIPELINE_PATH is set
            os.environ["BOOK_PIPELINE_PATH"] = str(primary_path)
            result = get_test_book_path(validate_exists=False)
            self.assertEqual(result.resolve(), primary_path.resolve())
            del os.environ["BOOK_PIPELINE_PATH"]

            # Test 2: Only CALIBRE_BOOKS_TEST_PATH is set
            os.environ["CALIBRE_BOOKS_TEST_PATH"] = str(fallback_path)
            result = get_test_book_path(validate_exists=False)
            self.assertEqual(result.resolve(), fallback_path.resolve())

            # Test 3: Both are set - BOOK_PIPELINE_PATH should win
            os.environ["BOOK_PIPELINE_PATH"] = str(primary_path)
            result = get_test_book_path(validate_exists=False)
            self.assertEqual(result.resolve(), primary_path.resolve())

            # Cleanup
            del os.environ["BOOK_PIPELINE_PATH"]
            del os.environ["CALIBRE_BOOKS_TEST_PATH"]

    def test_default_fallback(self):
        """Test that default path is used when nothing else is set."""
        # Ensure environment is clean
        if "CALIBRE_BOOKS_TEST_PATH" in os.environ:
            del os.environ["CALIBRE_BOOKS_TEST_PATH"]

        # Test path resolution with custom default
        custom_default = str(self.test_book_dir)
        result = get_test_book_path(default_path=custom_default)
        self.assertEqual(result.resolve(), self.test_book_dir.resolve())

    def test_validation_enabled(self):
        """Test that validation works when enabled."""
        # Use non-existent path
        nonexistent_path = "/this/path/does/not/exist"
        args = argparse.Namespace()
        args.book_path = nonexistent_path

        # Should raise FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            get_test_book_path(cli_args=args, validate_exists=True)

    def test_validation_disabled(self):
        """Test that validation can be disabled."""
        # Use non-existent path
        nonexistent_path = "/this/path/does/not/exist"
        args = argparse.Namespace()
        args.book_path = nonexistent_path

        # Should not raise an error when validation is disabled
        result = get_test_book_path(cli_args=args, validate_exists=False)
        self.assertEqual(result, Path(nonexistent_path))

    def test_empty_path_validation(self):
        """Test that empty paths are rejected."""
        # Test with empty environment variable
        os.environ["CALIBRE_BOOKS_TEST_PATH"] = ""

        # Should use default path when env var is empty
        result = get_test_book_path(
            default_path=str(self.test_book_dir), validate_exists=True
        )
        self.assertEqual(result.resolve(), self.test_book_dir.resolve())

    def test_custom_env_var(self):
        """Test using custom environment variable names."""
        custom_primary_var = "CUSTOM_BOOK_PATH_PRIMARY"
        custom_fallback_var = "CUSTOM_BOOK_PATH_FALLBACK"

        # Test custom primary environment variable
        os.environ[custom_primary_var] = str(self.test_book_dir)
        result = get_test_book_path(
            primary_env_var=custom_primary_var,
            fallback_env_var=custom_fallback_var,
        )
        self.assertEqual(result.resolve(), self.test_book_dir.resolve())
        del os.environ[custom_primary_var]

        # Test custom fallback environment variable
        os.environ[custom_fallback_var] = str(self.test_book_dir)
        result = get_test_book_path(
            primary_env_var=custom_primary_var,
            fallback_env_var=custom_fallback_var,
        )
        self.assertEqual(result.resolve(), self.test_book_dir.resolve())
        del os.environ[custom_fallback_var]

    def test_path_expansion(self):
        """Test that paths are properly expanded (~ and relative)."""
        # Test with ~ expansion
        args = argparse.Namespace()
        args.book_path = "~/test_books_expand"

        result = get_test_book_path(cli_args=args, validate_exists=False)
        self.assertTrue(str(result).startswith("/"))
        self.assertNotIn("~", str(result))


class TestArgumentParser(unittest.TestCase):
    """Test cases for argument parser integration."""

    def test_add_book_path_argument(self):
        """Test adding book path argument to parser."""
        parser = argparse.ArgumentParser()
        add_book_path_argument(parser)

        # Check that argument was added
        args = parser.parse_args(["--book-path", "/test/path"])
        self.assertEqual(args.book_path, "/test/path")

    def test_custom_help_text(self):
        """Test custom help text for argument."""
        parser = argparse.ArgumentParser()
        custom_help = "Custom help text for testing"
        add_book_path_argument(parser, help_text=custom_help)

        # Check that help was registered (basic check)
        help_output = parser.format_help()
        self.assertIn("--book-path", help_output)

    def test_custom_destination(self):
        """Test custom destination for argument."""
        parser = argparse.ArgumentParser()
        add_book_path_argument(parser, dest="custom_dest")

        args = parser.parse_args(["--book-path", "/test/path"])
        self.assertEqual(args.custom_dest, "/test/path")


class TestSingleBookPath(unittest.TestCase):
    """Test cases for single book path resolution."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_book_dir = Path(self.test_dir) / "test_books"
        self.test_book_dir.mkdir()

        # Create test book file
        self.single_book_rel_path = "single-book-test/sanderson_elantris.epub"
        self.single_book_full_path = self.test_book_dir / self.single_book_rel_path
        self.single_book_full_path.parent.mkdir(parents=True)
        self.single_book_full_path.touch()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.test_dir)

    def test_single_book_path_resolution(self):
        """Test resolving single book path."""
        result = get_single_book_path(
            self.test_book_dir, self.single_book_rel_path, validate_exists=True
        )
        self.assertEqual(result, self.single_book_full_path)

    def test_single_book_not_found(self):
        """Test single book path with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            get_single_book_path(
                self.test_book_dir, "nonexistent/book.epub", validate_exists=True
            )

    def test_single_book_no_validation(self):
        """Test single book path without validation."""
        result = get_single_book_path(
            self.test_book_dir, "nonexistent/book.epub", validate_exists=False
        )
        expected = self.test_book_dir / "nonexistent/book.epub"
        self.assertEqual(result, expected)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.test_book_dir = Path(self.test_dir) / "test_books"
        self.test_book_dir.mkdir()

        # Create test structure matching expected layout
        single_book_dir = self.test_book_dir / "single-book-test"
        single_book_dir.mkdir()
        (single_book_dir / "sanderson_elantris.epub").touch()

        # Create some additional test books
        (self.test_book_dir / "sanderson_mistborn1.epub").touch()
        (self.test_book_dir / "sanderson_stormlight1.epub").touch()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.test_dir)

    def test_complete_workflow(self):
        """Test the complete workflow from CLI args to book discovery."""
        # Simulate CLI args
        args = argparse.Namespace()
        args.book_path = str(self.test_book_dir)

        # Test main book directory resolution
        book_dir = get_test_book_path(cli_args=args)
        self.assertEqual(book_dir.resolve(), self.test_book_dir.resolve())

        # Test single book resolution
        single_book = get_single_book_path(book_dir)
        expected_single_book = (
            self.test_book_dir / "single-book-test/sanderson_elantris.epub"
        )
        self.assertEqual(single_book.resolve(), expected_single_book.resolve())

        # Test that directory contains expected books
        book_files = list(book_dir.glob("*.epub"))
        self.assertEqual(
            len(book_files), 2
        )  # Two main books, not counting the single-book-test

        # Test that single book test directory exists and contains the test book
        single_test_files = list((book_dir / "single-book-test").glob("*.epub"))
        self.assertEqual(len(single_test_files), 1)

    def test_backward_compatibility(self):
        """Test that the solution maintains backward compatibility."""
        # Test with no CLI args or environment - should use default
        result = get_test_book_path(
            default_path=str(self.test_book_dir), validate_exists=True
        )
        self.assertEqual(result.resolve(), self.test_book_dir.resolve())


if __name__ == "__main__":
    unittest.main()
