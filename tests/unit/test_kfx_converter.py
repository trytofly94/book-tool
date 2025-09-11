"""
Unit tests for KFXConverter class and ConfigManager interface.

This module tests the fix for GitHub Issue #1 where KFX conversion fails
with "'ConfigManager' object has no attribute 'get'" error.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, Any

from calibre_books.config.manager import ConfigManager
from calibre_books.core.book import Book, BookMetadata, BookFormat
from calibre_books.core.conversion.kfx import KFXConverter


class TestKFXConverterInitialization:
    """Test KFXConverter initialization with ConfigManager."""

    def create_test_config_file(self, config_data: Dict[str, Any]) -> Path:
        """Create a temporary configuration file."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, temp_file)
        temp_file.close()
        return Path(temp_file.name)

    def test_kfx_converter_initialization_with_complete_config(self):
        """Test KFXConverter initializes correctly with complete configuration."""
        # Create test configuration with conversion section
        config_data = {
            "download": {
                "default_format": "epub",
                "download_path": "~/Books",
                "librarian_path": "librarian",
            },
            "calibre": {"library_path": "~/Calibre-Library", "cli_path": "auto"},
            "conversion": {
                "max_parallel": 6,
                "output_path": "~/Converted-Books",
                "kfx_plugin_required": True,
            },
            "asin_lookup": {
                "cache_path": "~/.calibre-books/cache/asin_cache.json",
                "sources": ["amazon", "goodreads"],
                "rate_limit": 2.0,
            },
            "logging": {
                "level": "INFO",
                "file": "~/logs/calibre-books.log",
                "format": "detailed",
            },
        }

        config_file = self.create_test_config_file(config_data)
        try:
            config_manager = ConfigManager(config_file)

            # Initialize KFXConverter - this should NOT raise AttributeError
            converter = KFXConverter(config_manager)

            # Verify initialization succeeded
            assert converter.config_manager == config_manager
            assert converter.max_workers == 6  # From conversion config
            assert hasattr(converter, "calibre_config")
        finally:
            config_file.unlink()

    def test_kfx_converter_initialization_with_missing_conversion_config(self):
        """Test KFXConverter handles missing conversion configuration gracefully."""
        # Create test configuration WITHOUT conversion section
        config_data = {
            "download": {
                "default_format": "epub",
                "download_path": "~/Books",
                "librarian_path": "librarian",
            },
            "calibre": {"library_path": "~/Calibre-Library", "cli_path": "auto"},
            "logging": {
                "level": "INFO",
                "file": "~/logs/calibre-books.log",
                "format": "detailed",
            },
        }

        config_file = self.create_test_config_file(config_data)
        try:
            config_manager = ConfigManager(config_file)

            # Initialize KFXConverter - should use defaults when conversion config is missing
            converter = KFXConverter(config_manager)

            # Verify it falls back to defaults gracefully
            assert converter.config_manager == config_manager
            assert converter.max_workers == 4  # Default value
            assert hasattr(converter, "calibre_config")
        finally:
            config_file.unlink()

    def test_kfx_converter_initialization_with_empty_conversion_config(self):
        """Test KFXConverter handles empty conversion configuration."""
        # Create test configuration with empty conversion section
        config_data = {
            "download": {
                "default_format": "epub",
                "download_path": "~/Books",
                "librarian_path": "librarian",
            },
            "conversion": {},  # Empty conversion section
            "calibre": {"library_path": "~/Calibre-Library", "cli_path": "auto"},
        }

        config_file = self.create_test_config_file(config_data)
        try:
            config_manager = ConfigManager(config_file)

            # Should use default max_workers when not specified
            converter = KFXConverter(config_manager)

            assert converter.max_workers == 4  # Default value
        finally:
            config_file.unlink()

    def test_kfx_converter_initialization_without_config_file(self):
        """Test KFXConverter handles missing configuration file."""
        # Create ConfigManager with non-existent file
        non_existent_path = Path("/tmp/non_existent_config.yml")
        config_manager = ConfigManager(non_existent_path)

        # Should handle missing config file gracefully
        converter = KFXConverter(config_manager)

        # Should use all defaults
        assert converter.max_workers == 4
        assert converter.calibre_config == {}


class TestKFXConverterConfigManagerInterface:
    """Test the specific fix for GitHub Issue #1."""

    def test_issue_1_config_manager_get_attribute_error_fixed(self):
        """Test that the original AttributeError no longer occurs.

        This test specifically verifies that the bug described in GitHub Issue #1
        ('ConfigManager' object has no attribute 'get') has been fixed.
        """
        # Create minimal config
        config_data = {
            "conversion": {"max_parallel": 8},
            "calibre": {"library_path": "~/test"},
        }

        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()

        try:
            config_manager = ConfigManager(Path(config_file.name))

            # Verify ConfigManager doesn't have 'get' method (the source of the original bug)
            assert not hasattr(config_manager, "get")

            # This should NOT raise AttributeError: 'ConfigManager' object has no attribute 'get'
            try:
                converter = KFXConverter(config_manager)
                # If we get here, the bug is fixed
                assert converter.max_workers == 8
                assert converter.config_manager == config_manager
            except AttributeError as e:
                if "'ConfigManager' object has no attribute 'get'" in str(e):
                    pytest.fail(f"GitHub Issue #1 bug still exists: {e}")
                else:
                    # Re-raise if it's a different AttributeError
                    raise
        finally:
            Path(config_file.name).unlink()

    def test_config_manager_interface_methods(self):
        """Test that ConfigManager methods work as expected by KFXConverter."""
        config_data = {
            "conversion": {
                "max_parallel": 12,
                "output_path": "~/test-output",
                "kfx_plugin_required": False,
            },
            "calibre": {
                "library_path": "~/test-library",
                "cli_path": "/usr/local/bin/calibre",
            },
        }

        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()

        try:
            config_manager = ConfigManager(Path(config_file.name))

            # Test the interface methods that KFXConverter uses
            conversion_config = config_manager.get_conversion_config()
            calibre_config = config_manager.get_calibre_config()

            # Verify the interface methods return dictionaries with get() method
            assert isinstance(conversion_config, dict)
            assert isinstance(calibre_config, dict)
            assert hasattr(conversion_config, "get")
            assert hasattr(calibre_config, "get")

            # Verify the specific pattern that was failing works
            max_parallel = conversion_config.get("max_parallel", 4)
            assert max_parallel == 12

            # Initialize converter and verify it uses the correct values
            converter = KFXConverter(config_manager)
            assert converter.max_workers == 12
        finally:
            Path(config_file.name).unlink()


class TestKFXConverterErrorHandling:
    """Test error handling scenarios in KFXConverter."""

    def test_config_manager_method_exception_handling(self):
        """Test that KFXConverter handles exceptions from ConfigManager methods."""
        # Create a mock ConfigManager that raises exceptions
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.side_effect = Exception(
            "Config error"
        )
        mock_config_manager.get_calibre_config.side_effect = Exception(
            "Calibre config error"
        )

        # Should not raise exception, should use defaults when config methods fail
        converter = KFXConverter(mock_config_manager)

        # Should have fallen back to defaults
        assert converter.max_workers == 4
        assert converter.calibre_config == {}

    def test_kfx_converter_with_valid_config(self):
        """Test KFXConverter handles valid configuration correctly."""
        config_data = {
            "conversion": {"max_parallel": 6},
            "calibre": {"library_path": "~/test"},
        }

        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()

        try:
            config_manager = ConfigManager(Path(config_file.name))

            # Should handle valid configuration correctly
            converter = KFXConverter(config_manager)

            assert converter.max_workers == 6  # Config should be loaded
            assert hasattr(converter, "_format_converter")  # Should have base converter
        finally:
            Path(config_file.name).unlink()


class TestKFXConverterSystemRequirements:
    """Test system requirements checking."""

    @patch("subprocess.run")
    def test_check_system_requirements_all_available(self, mock_run):
        """Test system requirements check when all tools are available."""
        # Mock successful subprocess calls
        mock_run.return_value = Mock(
            returncode=0, stdout="KFX Output (2, 17, 1) - Convert ebooks to KFX format"
        )

        config_data = {"conversion": {"max_parallel": 4}}
        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()

        try:
            config_manager = ConfigManager(Path(config_file.name))
            converter = KFXConverter(config_manager)

            # Mock subprocess calls for system requirements
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=0, stdout="KFX Output - Convert ebooks to KFX format"
                )

                requirements = converter.check_system_requirements()

                # Base requirements should be available with successful mock
                assert requirements["calibre"] is True
                assert requirements["ebook-convert"] is True
                assert requirements["kfx_plugin"] is True
                # KFX-specific requirements
                assert "kfx_plugin_advanced" in requirements
                assert "kindle_previewer" in requirements
                assert "library_access" in requirements
        finally:
            Path(config_file.name).unlink()

    @patch("subprocess.run")
    def test_check_system_requirements_missing_tools(self, mock_run):
        """Test system requirements check when tools are missing."""
        # Mock failed subprocess calls
        mock_run.side_effect = FileNotFoundError("Command not found")

        config_data = {"conversion": {"max_parallel": 4}}
        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()

        try:
            config_manager = ConfigManager(Path(config_file.name))
            converter = KFXConverter(config_manager)

            requirements = converter.check_system_requirements()

            # With failed subprocess calls, tools should show as unavailable
            assert requirements["calibre"] is False
            assert requirements["ebook-convert"] is False
            assert requirements["kfx_plugin"] is False
            # KFX-specific requirements should also fail
            assert requirements["kfx_plugin_advanced"] is False
            assert requirements["kindle_previewer"] is False
            assert requirements["library_access"] is False
        finally:
            Path(config_file.name).unlink()


class TestKFXConverterBookConversion:
    """Test book conversion functionality."""

    def create_test_book(self, title: str = "Test Book") -> Book:
        """Create a test book object."""
        metadata = BookMetadata(
            title=title, author="Test Author", format=BookFormat.EPUB
        )

        # Create a temporary test file
        temp_file = tempfile.NamedTemporaryFile(suffix=".epub", delete=False)
        temp_file.write(b"test content")
        temp_file.close()

        return Book(metadata=metadata, file_path=Path(temp_file.name))

    def test_convert_books_with_valid_setup(self):
        """Test book conversion with valid setup."""
        config_data = {"conversion": {"max_parallel": 2}}
        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()

        try:
            config_manager = ConfigManager(Path(config_file.name))
            converter = KFXConverter(config_manager)

            # Create test book that actually exists
            test_book = self.create_test_book()
            try:
                # Test dry run to avoid actual conversion
                results = converter.convert_books_to_kfx([test_book], dry_run=True)

                assert len(results) == 1
                assert results[0].success  # Dry run should succeed
                assert results[0].output_format == BookFormat.KFX
            finally:
                test_book.file_path.unlink()  # Clean up test file
        finally:
            Path(config_file.name).unlink()

    def test_convert_books_with_missing_files(self):
        """Test book conversion with missing source files."""
        config_data = {"conversion": {"max_parallel": 2}}
        config_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, config_file)
        config_file.close()

        try:
            config_manager = ConfigManager(Path(config_file.name))
            converter = KFXConverter(config_manager)

            # Create book with non-existent file
            metadata = BookMetadata(
                title="Missing Book", author="Test Author", format=BookFormat.EPUB
            )

            book = Book(metadata=metadata, file_path=Path("/non/existent/file.epub"))

            results = converter.convert_books_to_kfx([book])

            assert len(results) == 1
            assert not results[0].success
            assert "Source file not found" in results[0].error
        finally:
            Path(config_file.name).unlink()
