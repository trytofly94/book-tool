"""
Unit tests for configuration management.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from calibre_books.config.manager import ConfigManager
from calibre_books.config.schema import ConfigurationSchema


class TestConfigManager:
    """Test ConfigManager functionality."""
    
    def test_config_manager_init(self):
        """Test ConfigManager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yml"
            manager = ConfigManager(config_path)
            
            # Path may be resolved differently (e.g., /private/var vs /var)
            assert manager.config_path.name == config_path.name
            assert manager.config_path.is_absolute()
    
    def test_load_nonexistent_config(self):
        """Test handling of nonexistent configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "nonexistent.yml"
            manager = ConfigManager(config_path)
            
            # Should raise FileNotFoundError when file doesn't exist
            with pytest.raises(FileNotFoundError):
                manager.get_config()
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yml"
            manager = ConfigManager(config_path)
            
            # Create test configuration
            test_config = {
                'download': {
                    'default_format': 'epub',
                    'download_path': '~/Books',
                    'librarian_path': 'librarian'
                },
                'logging': {
                    'level': 'DEBUG',
                    'file': '~/logs/test.log',
                    'format': 'simple'
                }
            }
            
            # Save configuration
            manager.save_config(test_config)
            
            # Create new manager and load
            new_manager = ConfigManager(config_path)
            loaded_config = new_manager.get_config()
            
            assert loaded_config['download']['default_format'] == 'epub'
            assert loaded_config['logging']['level'] == 'DEBUG'
    
    def test_specific_config_getters(self):
        """Test specific configuration getters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yml"
            manager = ConfigManager(config_path)
            
            # Create test configuration with all sections
            test_config = {
                'download': {
                    'default_format': 'epub',
                    'download_path': '~/Books',
                    'librarian_path': 'librarian'
                },
                'calibre': {
                    'library_path': '~/Calibre-Library',
                    'cli_path': 'auto'
                },
                'asin_lookup': {
                    'cache_path': '~/.calibre-books/cache/asin_cache.json',
                    'sources': ['amazon', 'goodreads'],
                    'rate_limit': 2.0
                },
                'conversion': {
                    'max_parallel': 4,
                    'output_path': '~/Converted-Books',
                    'kfx_plugin_required': True
                },
                'logging': {
                    'level': 'DEBUG',
                    'file': '~/logs/test.log',
                    'format': 'simple'
                }
            }
            
            manager.save_config(test_config)
            
            # Test specific getters
            download_config = manager.get_download_config()
            assert download_config['default_format'] == 'epub'
    
    def test_invalid_config_value(self):
        """Test handling of invalid configuration values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yml"
            manager = ConfigManager(config_path)
            
            # Invalid config should raise error during validation
            invalid_config = {
                'download': {
                    'default_format': 'invalid_format',  # Invalid format
                    'download_path': '~/Books',
                    'librarian_path': 'librarian'
                }
            }
            
            with pytest.raises(ValueError):  # Will be validation error
                manager.save_config(invalid_config)
    
    def test_config_file_permissions(self):
        """Test configuration file permissions handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "subdir" / "config.yml"  # Non-existent subdir
            manager = ConfigManager(config_path)
            
            test_config = {
                'download': {
                    'default_format': 'mobi',
                    'download_path': '~/Books',
                    'librarian_path': 'librarian'
                }
            }
            
            # Save configuration (should create directory)
            manager.save_config(test_config)
            
            # Check that file was created
            assert config_path.exists()
            
            # Check that directory structure was created
            assert config_path.parent.exists()


class TestConfigurationSchema:
    """Test configuration schema validation."""
    
    def test_default_configuration(self):
        """Test default configuration creation."""
        config = ConfigurationSchema()
        
        assert config.download.default_format == "mobi"
        assert config.calibre.cli_path == "auto"
        assert config.asin_lookup.rate_limit == 2.0
        assert config.conversion.max_parallel == 4
        assert config.logging.level == "INFO"
    
    def test_download_config_validation(self):
        """Test download configuration validation."""
        # Valid format
        config = ConfigurationSchema()
        config.download.default_format = "epub"
        assert config.download.default_format == "epub"
        
        # Invalid format should raise error during validation
        with pytest.raises(ValueError):
            from calibre_books.config.schema import DownloadConfig
            DownloadConfig(default_format="invalid")
    
    def test_logging_config_validation(self):
        """Test logging configuration validation."""
        from calibre_books.config.schema import LoggingConfig
        
        # Valid level
        config = LoggingConfig(level="DEBUG")
        assert config.level == "DEBUG"
        
        # Invalid level should raise error
        with pytest.raises(ValueError):
            LoggingConfig(level="INVALID")
        
        # Valid format
        config = LoggingConfig(format="simple")
        assert config.format == "simple"
        
        # Invalid format should raise error
        with pytest.raises(ValueError):
            LoggingConfig(format="invalid")
    
    def test_asin_lookup_config_validation(self):
        """Test ASIN lookup configuration validation."""
        from calibre_books.config.schema import ASINLookupConfig
        
        # Valid sources
        config = ASINLookupConfig(sources=["amazon", "goodreads"])
        assert config.sources == ["amazon", "goodreads"]
        
        # Invalid source should raise error
        with pytest.raises(ValueError):
            ASINLookupConfig(sources=["invalid_source"])
    
    def test_conversion_config_validation(self):
        """Test conversion configuration validation."""
        from calibre_books.config.schema import ConversionConfig
        
        # Valid max_parallel
        config = ConversionConfig(max_parallel=8)
        assert config.max_parallel == 8
        
        # Invalid max_parallel (too high) should raise error
        with pytest.raises(ValueError):
            ConversionConfig(max_parallel=20)
        
        # Invalid max_parallel (too low) should raise error  
        with pytest.raises(ValueError):
            ConversionConfig(max_parallel=0)
    
    def test_path_expansion(self):
        """Test that paths are properly expanded."""
        from calibre_books.config.schema import CalibreConfig, ConversionConfig
        
        # Test library path expansion
        config = CalibreConfig(library_path="~/test")
        assert config.library_path.startswith("/")  # Should be expanded
        
        # Test output path expansion
        config = ConversionConfig(output_path="~/output")
        assert config.output_path.startswith("/")  # Should be expanded