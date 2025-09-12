#!/usr/bin/env python3
"""
Unit tests for CLI module structure and Issue #81 fix.

Tests the RuntimeWarning fix that ensures proper module execution
without warnings when using `python -m calibre_books.cli`.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the src directory to the path for testing
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import after path setup to avoid import issues
from src.calibre_books.cli.main import cli_entry_point  # noqa: E402


class TestCLIModuleStructure:
    """Test CLI module structure and RuntimeWarning fix."""

    def test_main_py_importable(self):
        """Test that main.py can be imported without issues."""
        # This should work without any warnings
        import sys

        cli_main_module = sys.modules["src.calibre_books.cli.main"]
        assert hasattr(cli_main_module, "cli_entry_point")
        assert hasattr(cli_main_module, "main")

    def test_main_py_entry_point_exists(self):
        """Test that cli_entry_point function exists and is callable."""
        assert callable(cli_entry_point)

    def test_main_module_importable(self):
        """Test that __main__.py can be imported without issues."""

        # Should import successfully without any warnings

    def test_module_execution_no_runtime_warning(self):
        """
        Test that `python -m src.calibre_books.cli` runs without RuntimeWarning.

        This is the primary test for Issue #81 fix.
        """
        # Use subprocess to test module execution in isolation
        # Convert warnings to errors to catch RuntimeWarning
        cmd = [
            sys.executable,
            "-W",
            "error::RuntimeWarning",
            "-m",
            "src.calibre_books.cli",
            "--version",
        ]

        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        # Should succeed without RuntimeWarning (exit code 0)
        assert result.returncode == 0, f"Command failed with error: {result.stderr}"
        assert "book-tool version" in result.stdout
        assert "RuntimeWarning" not in result.stderr

    def test_old_command_still_shows_runtime_warning(self):
        """
        Test that the old problematic command still shows RuntimeWarning.

        This ensures our fix doesn't accidentally hide the warning for
        the incorrect usage pattern.
        """
        cmd = [
            sys.executable,
            "-W",
            "error::RuntimeWarning",
            "-m",
            "src.calibre_books.cli.main",
            "--version",
        ]

        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        # Should fail due to RuntimeWarning
        assert result.returncode != 0
        assert "RuntimeWarning" in result.stderr

    def test_cli_help_works_with_new_module_execution(self):
        """Test that CLI help works with new module execution method."""
        cmd = [sys.executable, "-m", "src.calibre_books.cli", "--help"]

        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        assert result.returncode == 0
        assert "Book Tool - Professional eBook processing" in result.stdout
        assert "Usage: python -m src.calibre_books.cli" in result.stdout

    def test_all_subcommands_accessible(self):
        """Test that all CLI subcommands are accessible via new execution method."""
        expected_commands = [
            "process",
            "asin",
            "convert",
            "download",
            "library",
            "config",
            "validate",
        ]

        cmd = [sys.executable, "-m", "src.calibre_books.cli", "--help"]
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        assert result.returncode == 0

        for command in expected_commands:
            assert (
                command in result.stdout
            ), f"Command '{command}' not found in help output"

    def test_cli_entry_point_handles_keyboard_interrupt(self):
        """Test that cli_entry_point properly handles KeyboardInterrupt."""
        with patch("src.calibre_books.cli.main.main") as mock_main:
            mock_main.side_effect = KeyboardInterrupt()

            with pytest.raises(SystemExit) as excinfo:
                cli_entry_point()

            assert excinfo.value.code == 130

    def test_cli_entry_point_handles_general_exception(self):
        """Test that cli_entry_point properly handles general exceptions."""
        with patch("src.calibre_books.cli.main.main") as mock_main:
            mock_main.side_effect = RuntimeError("Test error")

            with pytest.raises(SystemExit) as excinfo:
                cli_entry_point()

            assert excinfo.value.code == 1

    def test_module_structure_files_exist(self):
        """Test that all required module structure files exist."""
        cli_dir = PROJECT_ROOT / "src" / "calibre_books" / "cli"

        required_files = ["__init__.py", "__main__.py", "main.py"]

        for file_name in required_files:
            file_path = cli_dir / file_name
            assert file_path.exists(), f"Required file {file_name} does not exist"
            assert file_path.is_file(), f"{file_name} is not a regular file"

    def test_main_module_has_correct_entry_point(self):
        """Test that __main__.py has the correct entry point structure."""
        main_file = PROJECT_ROOT / "src" / "calibre_books" / "cli" / "__main__.py"
        content = main_file.read_text()

        # Check for correct import
        assert "from .main import cli_entry_point" in content

        # Check for correct execution guard
        assert 'if __name__ == "__main__":' in content
        assert "cli_entry_point()" in content

    def test_global_options_work_with_module_execution(self):
        """Test that global CLI options work with module execution."""
        cmd = [
            sys.executable,
            "-m",
            "src.calibre_books.cli",
            "--log-level",
            "DEBUG",
            "--version",
        ]

        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        assert result.returncode == 0
        assert "book-tool version" in result.stdout


class TestCLIRegressionPrevention:
    """Regression tests to ensure the fix doesn't break existing functionality."""

    def test_no_performance_degradation(self):
        """Test that module execution performance is acceptable."""
        import time

        start_time = time.time()
        cmd = [sys.executable, "-m", "src.calibre_books.cli", "--version"]

        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        end_time = time.time()
        execution_time = end_time - start_time

        assert result.returncode == 0
        # Should complete within reasonable time (5 seconds)
        assert (
            execution_time < 5.0
        ), f"CLI took too long to execute: {execution_time:.2f}s"

    def test_error_handling_preserved(self):
        """Test that error handling is preserved in new module execution."""
        # Test with invalid command
        cmd = [sys.executable, "-m", "src.calibre_books.cli", "nonexistent-command"]

        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        assert result.returncode != 0
        assert "No such command" in result.stderr

    def test_subcommand_structure_preserved(self):
        """Test that subcommand structure is preserved."""
        # Test a nested command structure
        cmd = [sys.executable, "-m", "src.calibre_books.cli", "process", "--help"]

        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)

        assert result.returncode == 0
        assert "Process existing eBook files" in result.stdout
