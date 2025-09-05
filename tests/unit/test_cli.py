"""
Unit tests for CLI functionality.
"""

import pytest
from click.testing import CliRunner

from calibre_books.cli.main import main


class TestCLIEntryPoint:
    """Test CLI entry point functionality."""
    
    def test_cli_help(self):
        """Test CLI help display."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])
        
        assert result.exit_code == 0
        assert 'Calibre Books CLI Tool' in result.output
        assert 'download' in result.output
        assert 'asin' in result.output
        assert 'convert' in result.output
        assert 'config' in result.output
    
    def test_cli_version(self):
        """Test version display."""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])
        
        assert result.exit_code == 0
        assert 'calibre-books version' in result.output
    
    def test_cli_no_command_shows_help(self):
        """Test that running without command shows help."""
        runner = CliRunner()
        result = runner.invoke(main, [])
        
        assert result.exit_code == 0
        assert 'Calibre Books CLI Tool' in result.output
        assert 'download' in result.output


class TestCommandGroups:
    """Test individual command groups."""
    
    def test_download_help(self):
        """Test download command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['download', '--help'])
        
        assert result.exit_code == 0
        assert 'Download books from various sources' in result.output
    
    def test_asin_help(self):
        """Test asin command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['asin', '--help'])
        
        assert result.exit_code == 0
        assert 'Manage ASINs and book metadata' in result.output
    
    def test_convert_help(self):
        """Test convert command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['convert', '--help'])
        
        assert result.exit_code == 0
        assert 'Convert book formats' in result.output
    
    def test_config_help(self):
        """Test config command help."""
        runner = CliRunner()
        result = runner.invoke(main, ['config', '--help'])
        
        assert result.exit_code == 0
        assert 'Manage configuration settings' in result.output