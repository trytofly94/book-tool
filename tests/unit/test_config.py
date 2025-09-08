"""
Unit tests for configuration management.
"""

import pytest
import tempfile
from pathlib import Path

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
                "download": {
                    "default_format": "epub",
                    "download_path": "~/Books",
                    "librarian_path": "librarian",
                },
                "logging": {
                    "level": "DEBUG",
                    "file": "~/logs/test.log",
                    "format": "simple",
                },
            }

            # Save configuration
            manager.save_config(test_config)

            # Create new manager and load
            new_manager = ConfigManager(config_path)
            loaded_config = new_manager.get_config()

            assert loaded_config["download"]["default_format"] == "epub"
            assert loaded_config["logging"]["level"] == "DEBUG"

    def test_specific_config_getters(self):
        """Test specific configuration getters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yml"
            manager = ConfigManager(config_path)

            # Create test configuration with all sections
            test_config = {
                "download": {
                    "default_format": "epub",
                    "download_path": "~/Books",
                    "librarian_path": "librarian",
                },
                "calibre": {"library_path": "~/Calibre-Library", "cli_path": "auto"},
                "asin_lookup": {
                    "cache_path": "~/.calibre-books/cache/asin_cache.json",
                    "sources": ["amazon", "goodreads"],
                    "rate_limit": 2.0,
                },
                "conversion": {
                    "max_parallel": 4,
                    "output_path": "~/Converted-Books",
                    "kfx_plugin_required": True,
                },
                "logging": {
                    "level": "DEBUG",
                    "file": "~/logs/test.log",
                    "format": "simple",
                },
            }

            manager.save_config(test_config)

            # Test specific getters
            download_config = manager.get_download_config()
            assert download_config["default_format"] == "epub"

    def test_invalid_config_value(self):
        """Test handling of invalid configuration values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yml"
            manager = ConfigManager(config_path)

            # Invalid config should raise error during validation
            invalid_config = {
                "download": {
                    "default_format": "invalid_format",  # Invalid format
                    "download_path": "~/Books",
                    "librarian_path": "librarian",
                }
            }

            with pytest.raises(ValueError):  # Will be validation error
                manager.save_config(invalid_config)

    def test_config_file_permissions(self):
        """Test configuration file permissions handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = (
                Path(temp_dir) / "subdir" / "config.yml"
            )  # Non-existent subdir
            manager = ConfigManager(config_path)

            test_config = {
                "download": {
                    "default_format": "mobi",
                    "download_path": "~/Books",
                    "librarian_path": "librarian",
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

    def test_download_config_validation(self):
        """Test download configuration validation."""
        from calibre_books.config.schema import DownloadConfig

        # Valid configuration
        config = DownloadConfig(
            default_format="epub",
            download_path="~/Books",
            librarian_path="librarian",
            max_parallel=4,
            quality="medium",
            search_timeout=120,
            download_timeout=600,
        )

        assert config.default_format == "epub"
        assert config.max_parallel == 4
        assert config.quality == "medium"
        assert config.search_timeout == 120
        assert config.download_timeout == 600
        assert config.download_path.startswith("/")  # Path should be expanded

    def test_download_config_invalid_format(self):
        """Test download configuration with invalid format."""
        from calibre_books.config.schema import DownloadConfig

        with pytest.raises(ValueError, match="Invalid format"):
            DownloadConfig(default_format="invalid_format")

    def test_download_config_invalid_quality(self):
        """Test download configuration with invalid quality."""
        from calibre_books.config.schema import DownloadConfig

        with pytest.raises(ValueError, match="Invalid quality"):
            DownloadConfig(quality="invalid_quality")

    def test_download_config_invalid_max_parallel(self):
        """Test download configuration with invalid max_parallel."""
        from calibre_books.config.schema import DownloadConfig

        # Too low
        with pytest.raises(ValueError):
            DownloadConfig(max_parallel=0)

        # Too high
        with pytest.raises(ValueError):
            DownloadConfig(max_parallel=10)

    def test_download_config_invalid_timeouts(self):
        """Test download configuration with invalid timeout values."""
        from calibre_books.config.schema import DownloadConfig

        # Search timeout too low
        with pytest.raises(ValueError):
            DownloadConfig(search_timeout=5)

        # Search timeout too high
        with pytest.raises(ValueError):
            DownloadConfig(search_timeout=400)

        # Download timeout too low
        with pytest.raises(ValueError):
            DownloadConfig(download_timeout=30)

        # Download timeout too high
        with pytest.raises(ValueError):
            DownloadConfig(download_timeout=4000)

    def test_download_config_format_case_normalization(self):
        """Test that format is normalized to lowercase."""
        from calibre_books.config.schema import DownloadConfig

        config = DownloadConfig(default_format="EPUB")
        assert config.default_format == "epub"

        config = DownloadConfig(default_format="MobI")
        assert config.default_format == "mobi"

    def test_download_config_quality_case_normalization(self):
        """Test that quality is normalized to lowercase."""
        from calibre_books.config.schema import DownloadConfig

        config = DownloadConfig(quality="HIGH")
        assert config.quality == "high"

        config = DownloadConfig(quality="Medium")
        assert config.quality == "medium"

    def test_download_config_defaults(self):
        """Test download configuration default values."""
        from calibre_books.config.schema import DownloadConfig

        config = DownloadConfig()

        assert config.default_format == "mobi"
        assert config.download_path.endswith("Downloads/Books")
        assert config.librarian_path == "librarian"
        assert config.max_parallel == 1
        assert config.quality == "high"
        assert config.search_timeout == 60
        assert config.download_timeout == 300

    def test_full_configuration_schema_with_download(self):
        """Test full configuration schema including download section."""
        test_config = {
            "download": {
                "default_format": "epub",
                "download_path": "~/TestBooks",
                "librarian_path": "/usr/local/bin/librarian",
                "max_parallel": 3,
                "quality": "medium",
                "search_timeout": 90,
                "download_timeout": 450,
            },
            "calibre": {"library_path": "~/TestLibrary"},
        }

        validated = ConfigurationSchema.validate_config(test_config)

        assert validated["download"]["default_format"] == "epub"
        assert validated["download"]["max_parallel"] == 3
        assert validated["download"]["quality"] == "medium"
        assert validated["download"]["download_path"].endswith("TestBooks")

    def test_minimal_config_includes_download(self):
        """Test that minimal configuration includes download settings."""
        minimal_config = ConfigurationSchema.get_minimal_config()

        assert "download" in minimal_config
        assert minimal_config["download"]["default_format"] == "mobi"
        assert minimal_config["download"]["max_parallel"] == 1
