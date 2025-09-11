"""
Unit tests for CLI functionality.
"""

from click.testing import CliRunner

from calibre_books.cli.main import main, cli_entry_point
from calibre_books.cli.__main__ import main as main_entry


class TestCLIEntryPoint:
    """Test CLI entry point functionality."""

    def test_cli_help(self):
        """Test CLI help display."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Book Tool - Professional eBook processing" in result.output
        assert "process" in result.output
        assert "asin" in result.output
        assert "convert" in result.output
        assert "config" in result.output

    def test_cli_version(self):
        """Test version display."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "book-tool version" in result.output

    def test_cli_no_command_shows_help(self):
        """Test that running without command shows help."""
        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code == 0
        assert "Book Tool" in result.output
        assert "process" in result.output


class TestCommandGroups:
    """Test individual command groups."""

    def test_process_help(self):
        """Test process command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["process", "--help"])

        assert result.exit_code == 0
        assert "Process existing eBook files" in result.output

    def test_asin_help(self):
        """Test asin command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["asin", "--help"])

        assert result.exit_code == 0
        assert "Manage ASINs and book metadata" in result.output

    def test_convert_help(self):
        """Test convert command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["convert", "--help"])

        assert result.exit_code == 0
        assert "Convert book formats" in result.output

    def test_config_help(self):
        """Test config command help."""
        runner = CliRunner()
        result = runner.invoke(main, ["config", "--help"])

        assert result.exit_code == 0
        assert "Manage configuration settings" in result.output


class TestMainModuleExecution:
    """Test the new __main__.py module execution functionality."""

    def test_main_entry_function(self):
        """Test that __main__.main() function works correctly."""
        # Since main_entry just calls cli_entry_point, we can test it indirectly
        # by ensuring the import works and the function exists
        assert callable(main_entry)
        assert main_entry.__name__ == "main"

    def test_cli_entry_point_function(self):
        """Test cli_entry_point function exists and is callable."""
        assert callable(cli_entry_point)
        assert cli_entry_point.__name__ == "cli_entry_point"
