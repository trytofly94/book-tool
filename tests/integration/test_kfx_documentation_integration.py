"""
Integration tests for KFX plugin documentation and CLI integration.

Tests the complete user experience for KFX plugin validation,
error messages, and documentation integration.
"""

from unittest.mock import Mock, patch, MagicMock
import pytest
import subprocess
from click.testing import CliRunner
from pathlib import Path

from calibre_books.cli.convert import convert
from calibre_books.cli.config import config
from calibre_books.config.manager import ConfigManager


class TestKFXDocumentationIntegration:
    """Test KFX documentation integration with CLI commands."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager for CLI testing."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_config_path.return_value = Path("~/.book-tool/config.yaml")
        config_manager.get_conversion_config.return_value = {
            'max_parallel': 4,
            'output_path': '~/Converted-Books',
            'kfx_plugin_required': True
        }
        config_manager.get_calibre_config.return_value = {}
        return config_manager
    
    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()
    
    @pytest.fixture
    def temp_input_dir(self, tmp_path):
        """Create temporary input directory with mock books."""
        input_dir = tmp_path / "books"
        input_dir.mkdir()
        
        # Create mock book files
        (input_dir / "test_book.epub").touch()
        (input_dir / "another_book.mobi").touch()
        
        return input_dir


class TestKFXConversionCLIPluginValidation(TestKFXDocumentationIntegration):
    """Test KFX conversion CLI commands with plugin validation."""
    
    def test_kfx_conversion_fails_gracefully_without_plugin(
        self, runner, temp_input_dir, mock_config_manager
    ):
        """Test that KFX conversion provides helpful error message when plugin missing."""
        
        # Mock the KFXConverter to simulate missing plugin
        with patch('calibre_books.cli.convert.FormatConverter') as mock_converter_class:
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            mock_converter.validate_kfx_plugin.return_value = False
            
            # Create mock context
            ctx = {'config': mock_config_manager, 'dry_run': False}
            
            result = runner.invoke(
                convert,
                ['kfx', '--input-dir', str(temp_input_dir)],
                obj=ctx,
                catch_exceptions=False
            )
            
            assert result.exit_code == 1
            assert "KFX Output plugin not found!" in result.output
            assert "Open Calibre → Preferences → Plugins" in result.output
            assert "Get new plugins → Search 'KFX Output'" in result.output
            assert "Install plugin by jhowell" in result.output
            assert "kfx-conversion-prerequisites" in result.output
    
    def test_kfx_conversion_proceeds_with_valid_plugin(
        self, runner, temp_input_dir, mock_config_manager
    ):
        """Test that KFX conversion proceeds when plugin is available."""
        
        # Mock FileScanner and KFXConverter 
        with patch('calibre_books.cli.convert.FileScanner') as mock_scanner_class, \
             patch('calibre_books.cli.convert.FormatConverter') as mock_converter_class, \
             patch('calibre_books.cli.convert.ProgressManager') as mock_progress:
            
            # Setup mocks
            mock_scanner = Mock()
            mock_scanner_class.return_value = mock_scanner
            mock_scanner.scan_directory.return_value = []  # No books found
            
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            mock_converter.validate_kfx_plugin.return_value = True
            
            # Create mock context
            ctx = {'config': mock_config_manager, 'dry_run': False}
            
            result = runner.invoke(
                convert,
                ['kfx', '--input-dir', str(temp_input_dir)],
                obj=ctx
            )
            
            # Should not exit with error, but find no books
            assert result.exit_code == 0
            assert "No convertible eBook files found" in result.output
            # Plugin validation should have been called
            mock_converter.validate_kfx_plugin.assert_called_once()
    
    def test_single_file_conversion_validates_plugin(
        self, runner, temp_input_dir, mock_config_manager
    ):
        """Test that single file KFX conversion validates plugin."""
        
        test_file = temp_input_dir / "test.epub"
        test_file.touch()
        
        with patch('calibre_books.cli.convert.FormatConverter') as mock_converter_class:
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            mock_converter.validate_kfx_plugin.return_value = False
            
            # Create mock context
            ctx = {'config': mock_config_manager, 'dry_run': False}
            
            result = runner.invoke(
                convert,
                ['single', '--input-file', str(test_file), '--format', 'kfx'],
                obj=ctx,
                catch_exceptions=False
            )
            
            assert result.exit_code == 1
            assert "KFX Output plugin not found!" in result.output
    
    def test_check_requirements_shows_plugin_status(
        self, runner, temp_input_dir, mock_config_manager
    ):
        """Test that --check-requirements shows KFX plugin status."""
        
        with patch('calibre_books.cli.convert.FormatConverter') as mock_converter_class:
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            mock_converter.validate_kfx_plugin.return_value = True
            mock_converter.check_system_requirements.return_value = {
                'calibre': True,
                'ebook-convert': True,
                'kfx_plugin': False,  # Plugin missing
                'kindle_previewer': True
            }
            
            # Create mock context
            ctx = {'config': mock_config_manager, 'dry_run': False}
            
            result = runner.invoke(
                convert,
                ['kfx', '--input-dir', str(temp_input_dir), '--check-requirements'],
                obj=ctx
            )
            
            assert result.exit_code == 0
            assert "System Requirements" in result.output
            assert "KFX Output Plugin for Calibre" in result.output
            assert "Missing requirements: kfx_plugin" in result.output


class TestConfigInitKFXPluginWarning(TestKFXDocumentationIntegration):
    """Test config initialization with KFX plugin warnings."""
    
    def test_config_init_warns_about_missing_kfx_plugin(
        self, runner, mock_config_manager, tmp_path
    ):
        """Test that config initialization warns about missing KFX plugin."""
        
        config_file = tmp_path / "config.yaml"
        mock_config_manager.get_config_path.return_value = config_file
        mock_config_manager.create_config = Mock()
        
        # Mock FormatConverter to simulate missing plugin
        with patch('calibre_books.cli.config.ConfigManager', return_value=mock_config_manager), \
             patch('calibre_books.core.converter.FormatConverter') as mock_converter_class:
            
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            mock_converter.validate_kfx_plugin.return_value = False
            
            # Create mock context
            ctx = {'dry_run': False}
            
            result = runner.invoke(
                config,
                ['init', '--minimal'],
                obj=ctx,
                input='y\n'  # Confirm overwrite if needed
            )
            
            assert result.exit_code == 0
            assert "Configuration initialized successfully!" in result.output
            assert "Warning: KFX Output plugin not detected" in result.output
            assert "KFX conversion will not work without this plugin" in result.output
            assert "Calibre → Preferences → Plugins → Get new plugins" in result.output
            assert "kfx-conversion-prerequisites" in result.output
    
    def test_config_init_no_warning_with_plugin_present(
        self, runner, mock_config_manager, tmp_path
    ):
        """Test that config initialization doesn't warn when plugin is present."""
        
        config_file = tmp_path / "config.yaml"
        mock_config_manager.get_config_path.return_value = config_file
        mock_config_manager.create_config = Mock()
        
        # Mock FormatConverter to simulate plugin present
        with patch('calibre_books.cli.config.ConfigManager', return_value=mock_config_manager), \
             patch('calibre_books.core.converter.FormatConverter') as mock_converter_class:
            
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            mock_converter.validate_kfx_plugin.return_value = True
            
            # Create mock context
            ctx = {'dry_run': False}
            
            result = runner.invoke(
                config,
                ['init', '--minimal'],
                obj=ctx,
                input='y\n'  # Confirm overwrite if needed
            )
            
            assert result.exit_code == 0
            assert "Configuration initialized successfully!" in result.output
            assert "Warning: KFX Output plugin not detected" not in result.output
    
    def test_config_init_continues_on_plugin_check_failure(
        self, runner, mock_config_manager, tmp_path
    ):
        """Test that config initialization continues even if plugin check fails."""
        
        config_file = tmp_path / "config.yaml"
        mock_config_manager.get_config_path.return_value = config_file
        mock_config_manager.create_config = Mock()
        
        # Mock FormatConverter to raise exception
        with patch('calibre_books.cli.config.ConfigManager', return_value=mock_config_manager), \
             patch('calibre_books.core.converter.FormatConverter', side_effect=Exception("Import error")):
            
            # Create mock context
            ctx = {'dry_run': False}
            
            result = runner.invoke(
                config,
                ['init', '--minimal'],
                obj=ctx,
                input='y\n'  # Confirm overwrite if needed
            )
            
            # Should still succeed despite plugin check failure
            assert result.exit_code == 0
            assert "Configuration initialized successfully!" in result.output
            # Should not show plugin warning due to exception handling
            assert "Warning: KFX Output plugin not detected" not in result.output


class TestHelpTextInclusion(TestKFXDocumentationIntegration):
    """Test that help text includes KFX plugin requirements."""
    
    def test_kfx_command_help_mentions_plugin_requirements(self, runner):
        """Test that KFX conversion help mentions plugin requirements."""
        
        result = runner.invoke(convert, ['kfx', '--help'])
        
        assert result.exit_code == 0
        assert "Convert eBook files to KFX format for Goodreads integration" in result.output
        assert "--check-requirements" in result.output
        assert "Check system requirements for KFX conversion" in result.output
    
    def test_single_command_help_shows_kfx_option(self, runner):
        """Test that single file conversion help shows KFX as format option."""
        
        result = runner.invoke(convert, ['single', '--help'])
        
        assert result.exit_code == 0
        assert "kfx" in result.output
        # Format choice should include kfx
        assert "--format" in result.output


class TestEndToEndValidation(TestKFXDocumentationIntegration):
    """Test complete end-to-end scenarios."""
    
    def test_complete_workflow_with_missing_plugin(
        self, runner, temp_input_dir, mock_config_manager
    ):
        """Test complete workflow: config init → KFX conversion with missing plugin."""
        
        # Step 1: Initialize config (should warn about missing plugin)
        config_file = temp_input_dir / "config.yaml" 
        mock_config_manager.get_config_path.return_value = config_file
        mock_config_manager.create_config = Mock()
        
        with patch('calibre_books.cli.config.ConfigManager', return_value=mock_config_manager), \
             patch('calibre_books.core.converter.FormatConverter') as mock_converter_class:
            
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            mock_converter.validate_kfx_plugin.return_value = False
            
            ctx = {'dry_run': False}
            
            config_result = runner.invoke(
                config,
                ['init', '--minimal'],
                obj=ctx
            )
            
            assert config_result.exit_code == 0
            assert "Warning: KFX Output plugin not detected" in config_result.output
        
        # Step 2: Attempt KFX conversion (should fail with helpful message)
        with patch('calibre_books.cli.convert.FormatConverter') as mock_converter_class:
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            mock_converter.validate_kfx_plugin.return_value = False
            
            ctx = {'config': mock_config_manager, 'dry_run': False}
            
            convert_result = runner.invoke(
                convert,
                ['kfx', '--input-dir', str(temp_input_dir)],
                obj=ctx,
                catch_exceptions=False
            )
            
            assert convert_result.exit_code == 1
            assert "KFX Output plugin required for KFX conversion" in convert_result.output


if __name__ == "__main__":
    pytest.main([__file__])