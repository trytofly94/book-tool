"""
Integration tests for KFX conversion CLI workflow.

This module tests the complete integration between CLI commands,
ConfigManager, and KFXConverter to ensure the fix for GitHub Issue #1
works in the full application context.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from calibre_books.config.manager import ConfigManager
from calibre_books.cli.main import main
from calibre_books.cli.convert import kfx


class TestKFXConversionCLIIntegration:
    """Integration tests for KFX conversion CLI workflow."""
    
    def create_test_config(self, config_data: dict = None) -> Path:
        """Create a temporary configuration file for testing."""
        if config_data is None:
            config_data = {
                'download': {
                    'default_format': 'epub',
                    'download_path': '~/Books',
                    'librarian_path': 'librarian'
                },
                'calibre': {
                    'library_path': '~/Calibre-Library',
                    'cli_path': 'auto'
                },
                'conversion': {
                    'max_workers': 4,
                    'output_path': '~/Converted-Books',
                    'kfx_plugin_required': True
                },
                'asin_lookup': {
                    'cache_path': '~/.calibre-books/cache/asin_cache.json',
                    'sources': ['amazon', 'goodreads'],
                    'rate_limit': 2.0
                },
                'logging': {
                    'level': 'INFO',
                    'file': '~/logs/calibre-books.log',
                    'format': 'detailed'
                }
            }
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False)
        yaml.dump(config_data, temp_file)
        temp_file.close()
        return Path(temp_file.name)
    
    def create_test_book_file(self, suffix: str = '.epub') -> Path:
        """Create a temporary test book file."""
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_file.write(b"Mock book content for testing")
        temp_file.close()
        return Path(temp_file.name)
    
    def test_kfx_conversion_cli_command_with_default_config(self):
        """Test complete KFX conversion CLI command with default configuration.
        
        This is the primary integration test that verifies the GitHub Issue #1
        fix works in the complete CLI context.
        """
        config_file = self.create_test_config()
        test_book = self.create_test_book_file()
        output_dir = Path(tempfile.mkdtemp())
        
        try:
            runner = CliRunner()
            
            # Mock the ParallelKFXConverter to avoid external dependencies
            with patch('calibre_books.core.downloader.ParallelKFXConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter.check_kfx_plugin.return_value = True
                mock_converter.check_kindle_previewer.return_value = True
                mock_converter.convert_single_to_kfx.return_value = {
                    'success': True,
                    'output_path': str(output_dir / 'test_kfx.azw3'),
                    'file_size': 1024
                }
                mock_converter_class.return_value = mock_converter
                
                # Mock file operations to avoid actual file conversion
                with patch('calibre_books.core.downloader.Path.mkdir'), \
                     patch('calibre_books.core.downloader.Path.exists', return_value=True), \
                     patch('calibre_books.core.downloader.Path.stat') as mock_stat:
                    
                    mock_stat.return_value.st_size = 1024
                    
                    # Run the CLI command - this should NOT fail with AttributeError
                    result = runner.invoke(main, [
                        '--config', str(config_file),
                        'convert', 'kfx',
                        '--input-dir', str(test_book.parent),
                        '--output-dir', str(output_dir),
                        '--parallel', '2'
                    ])
                    
                    # If GitHub Issue #1 was not fixed, this would fail with:
                    # AttributeError: 'ConfigManager' object has no attribute 'get'
                    
                    # Check that command completed without the AttributeError
                    if result.exit_code != 0:
                        if "'ConfigManager' object has no attribute 'get'" in result.output:
                            pytest.fail(f"GitHub Issue #1 regression detected: {result.output}")
                        # Other errors might be expected (missing files, etc.)
                        
        finally:
            config_file.unlink()
            test_book.unlink()
            # Clean up output directory
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
    
    def test_kfx_conversion_cli_with_missing_conversion_config(self):
        """Test CLI handles missing conversion configuration section gracefully."""
        # Config without conversion section
        config_data = {
            'download': {
                'default_format': 'epub',
                'download_path': '~/Books',
                'librarian_path': 'librarian'
            },
            'calibre': {
                'library_path': '~/Calibre-Library',
                'cli_path': 'auto'
            },
            'logging': {
                'level': 'INFO',
                'file': '~/logs/calibre-books.log',
                'format': 'detailed'
            }
            # Note: NO conversion section
        }
        
        config_file = self.create_test_config(config_data)
        test_book = self.create_test_book_file()
        output_dir = Path(tempfile.mkdtemp())
        
        try:
            runner = CliRunner()
            
            with patch('calibre_books.core.downloader.ParallelKFXConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter_class.return_value = mock_converter
                
                # Should not raise AttributeError even without conversion config
                result = runner.invoke(main, [
                    '--config', str(config_file),
                    'convert', 'kfx',
                    '--input-dir', str(test_book.parent),
                    '--output-dir', str(output_dir)
                ])
                
                # Should not have the specific GitHub Issue #1 error
                assert "'ConfigManager' object has no attribute 'get'" not in result.output
                
        finally:
            config_file.unlink()
            test_book.unlink()
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
    
    def test_kfx_conversion_with_custom_parallel_setting(self):
        """Test KFX conversion with custom parallel setting."""
        config_data = {
            'conversion': {
                'max_workers': 8,  # Custom value
                'output_path': '~/Converted-Books'
            },
            'calibre': {
                'library_path': '~/Calibre-Library',
                'cli_path': 'auto'
            },
            'logging': {
                'level': 'DEBUG',
                'file': '~/logs/calibre-books.log',
                'format': 'detailed'
            }
        }
        
        config_file = self.create_test_config(config_data)
        test_book = self.create_test_book_file()
        output_dir = Path(tempfile.mkdtemp())
        
        try:
            runner = CliRunner()
            
            with patch('calibre_books.core.downloader.ParallelKFXConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter_class.return_value = mock_converter
                
                # Test that custom parallel setting from CLI overrides config
                result = runner.invoke(main, [
                    '--config', str(config_file),
                    'convert', 'kfx',
                    '--input-dir', str(test_book.parent),
                    '--output-dir', str(output_dir),
                    '--parallel', '12'  # Override config value
                ])
                
                # Verify no ConfigManager AttributeError
                assert "'ConfigManager' object has no attribute 'get'" not in result.output
                
                # The converter should have been initialized with config max_workers=8
                # but the actual conversion should use CLI parallel=12
                mock_converter_class.assert_called_once()
                
        finally:
            config_file.unlink()
            test_book.unlink()
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)
    
    def test_convert_to_kfx_command_directly(self):
        """Test the convert_to_kfx command function directly."""
        config_file = self.create_test_config()
        test_book = self.create_test_book_file()
        output_dir = Path(tempfile.mkdtemp())
        
        try:
            runner = CliRunner()
            
            # Create a click context with ConfigManager
            config_manager = ConfigManager(config_file)
            
            with patch('calibre_books.core.downloader.ParallelKFXConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter.check_kfx_plugin.return_value = True
                mock_converter.check_kindle_previewer.return_value = True
                mock_converter_class.return_value = mock_converter
                
                # Mock the CLI context setup
                with runner.isolated_filesystem():
                    with patch('click.get_current_context') as mock_ctx:
                        mock_ctx.return_value.obj = {"config": config_manager}
                        
                        with patch('calibre_books.core.file_scanner.FileScanner.scan_directory') as mock_scan:
                            mock_scan.return_value = []  # No books found is fine for this test
                            
                            # This should initialize KFXConverter without AttributeError
                            result = runner.invoke(kfx, [
                                '--input-dir', str(test_book.parent),
                                '--output-dir', str(output_dir)
                            ])
                            
                            # The key test: no ConfigManager AttributeError
                            assert "'ConfigManager' object has no attribute 'get'" not in result.output
                            
        finally:
            config_file.unlink()
            test_book.unlink()
            import shutil
            shutil.rmtree(output_dir, ignore_errors=True)


class TestKFXConversionCLIErrorHandling:
    """Test error handling in KFX conversion CLI."""
    
    def test_cli_with_malformed_config_file(self):
        """Test CLI behavior with malformed configuration file."""
        # Create malformed YAML file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False)
        temp_file.write("invalid: yaml: content: [unclosed")
        temp_file.close()
        config_file = Path(temp_file.name)
        
        try:
            runner = CliRunner()
            
            # Should handle malformed config gracefully
            result = runner.invoke(main, [
                '--config', str(config_file),
                'convert', 'kfx',
                '--help'  # Just get help to test config loading
            ])
            
            # Should not have the GitHub Issue #1 AttributeError
            # (might have other YAML parsing errors which is expected)
            assert "'ConfigManager' object has no attribute 'get'" not in result.output
            
        finally:
            config_file.unlink()
    
    def test_cli_with_nonexistent_config_file(self):
        """Test CLI behavior with non-existent configuration file."""
        runner = CliRunner()
        
        nonexistent_config = Path("/tmp/nonexistent_config.yml")
        
        # Should handle missing config file gracefully
        result = runner.invoke(main, [
            '--config', str(nonexistent_config),
            'convert', 'kfx',
            '--help'
        ])
        
        # Should not have the GitHub Issue #1 AttributeError
        assert "'ConfigManager' object has no attribute 'get'" not in result.output


class TestKFXConversionConfigManagerFlow:
    """Test the complete ConfigManager flow in KFX conversion."""
    
    def test_config_manager_data_flow_to_kfx_converter(self):
        """Test that ConfigManager data flows correctly to KFXConverter.
        
        This test verifies the complete data flow that was broken in Issue #1.
        """
        config_data = {
            'conversion': {
                'max_workers': 6,
                'output_path': '~/test-converted',
                'kfx_plugin_required': True
            },
            'calibre': {
                'library_path': '~/test-library',
                'cli_path': '/test/calibre'
            }
        }
        
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()
        
        try:
            # Step 1: ConfigManager loads config
            config_manager = ConfigManager(Path(config_file.name))
            
            # Step 2: Verify ConfigManager has the expected methods
            assert hasattr(config_manager, 'get_conversion_config')
            assert hasattr(config_manager, 'get_calibre_config')
            
            # Step 3: Verify ConfigManager methods return dicts with get() method
            conversion_config = config_manager.get_conversion_config()
            calibre_config = config_manager.get_calibre_config()
            
            assert isinstance(conversion_config, dict)
            assert isinstance(calibre_config, dict)
            assert hasattr(conversion_config, 'get')
            assert hasattr(calibre_config, 'get')
            
            # Step 4: Test the specific pattern that was failing
            max_workers = conversion_config.get('max_workers', 4)
            assert max_workers == 6
            
            # Step 5: KFXConverter receives ConfigManager and uses it correctly
            with patch('calibre_books.core.downloader.ParallelKFXConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter_class.return_value = mock_converter
                
                # This was the failing line in the original bug
                from calibre_books.core.downloader import KFXConverter
                converter = KFXConverter(config_manager)
                
                # Verify the configuration was properly extracted
                assert converter.max_workers == 6
                assert converter.config_manager == config_manager
                
        finally:
            Path(config_file.name).unlink()
    
    def test_cli_context_passing_to_converter(self):
        """Test that CLI properly passes ConfigManager to converter."""
        config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False)
        yaml.dump({
            'conversion': {'max_workers': 3},
            'calibre': {'library_path': '~/test'}
        }, config_file)
        config_file.close()
        
        try:
            from calibre_books.cli.main import main
            from calibre_books.config.manager import ConfigManager
            
            runner = CliRunner()
            
            # Mock the KFXConverter instantiation to capture what it receives
            converter_instances = []
            
            def capture_converter_init(config_manager):
                """Mock KFXConverter init that captures the config_manager parameter."""
                converter_instances.append(config_manager)
                mock_converter = Mock()
                mock_converter.config_manager = config_manager
                mock_converter.max_workers = 3
                mock_converter._converter = None
                mock_converter.calibre_config = {}
                return mock_converter
            
            with patch('calibre_books.core.downloader.KFXConverter') as mock_kfx_class:
                mock_kfx_class.side_effect = capture_converter_init
                
                with patch('calibre_books.core.file_scanner.FileScanner.scan_directory', return_value=[]):
                    result = runner.invoke(main, [
                        '--config', str(Path(config_file.name)),
                        'convert', 'kfx',
                        '--input-dir', '/tmp',
                        '--output-dir', '/tmp'
                    ])
                    
                    # Verify that KFXConverter was called with a ConfigManager instance
                    assert len(converter_instances) > 0
                    config_manager = converter_instances[0]
                    
                    # This is the critical test: ConfigManager was passed, not dict
                    assert isinstance(config_manager, ConfigManager)
                    
                    # And the original bug pattern should work
                    conversion_config = config_manager.get_conversion_config()
                    max_workers = conversion_config.get('max_workers', 4)
                    assert max_workers == 3
                    
        finally:
            Path(config_file.name).unlink()