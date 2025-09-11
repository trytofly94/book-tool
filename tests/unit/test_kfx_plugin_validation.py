"""
Unit tests for KFX Output Plugin validation functionality.

Tests the plugin detection and validation system that ensures
the KFX Output plugin is installed and available in Calibre.
"""

import subprocess
from unittest.mock import Mock, patch
import pytest

from calibre_books.core.converter import FormatConverter
from calibre_books.config.manager import ConfigManager
from calibre_books.core.conversion.kfx import KFXConverter


class TestKFXPluginValidation:
    """Test KFX plugin validation functionality."""

    @pytest.fixture
    def mock_config_manager(self):
        """Mock ConfigManager for testing."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_conversion_config.return_value = {
            "max_parallel": 4,
            "output_path": "~/Converted-Books",
            "kfx_plugin_required": True,
        }
        config_manager.get_calibre_config.return_value = {}
        return config_manager

    @pytest.fixture
    def format_converter(self, mock_config_manager):
        """FormatConverter instance with mocked config."""
        return FormatConverter(mock_config_manager)

    @pytest.fixture
    def kfx_converter(self, mock_config_manager):
        """KFXConverter instance with mocked config."""
        return KFXConverter(mock_config_manager)


class TestFormatConverterPluginValidation(TestKFXPluginValidation):
    """Test plugin validation in FormatConverter."""

    def test_validate_kfx_plugin_success(self, format_converter):
        """Test successful KFX plugin detection."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "KFX Output (2, 17, 1) - Convert ebooks to KFX format"

        with patch("subprocess.run", return_value=mock_result):
            assert format_converter.validate_kfx_plugin() is True

    def test_validate_kfx_plugin_not_found(self, format_converter):
        """Test behavior when KFX plugin is not installed."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Some other plugin - Description"

        with patch("subprocess.run", return_value=mock_result):
            assert format_converter.validate_kfx_plugin() is False

    def test_validate_kfx_plugin_calibre_error(self, format_converter):
        """Test behavior when calibre-customize command fails."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Calibre command failed"

        with patch("subprocess.run", return_value=mock_result):
            assert format_converter.validate_kfx_plugin() is False

    def test_validate_kfx_plugin_timeout(self, format_converter):
        """Test behavior when calibre-customize times out."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("calibre-customize", 10),
        ):
            assert format_converter.validate_kfx_plugin() is False

    def test_validate_kfx_plugin_not_found_command(self, format_converter):
        """Test behavior when Calibre CLI tools are not available."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            assert format_converter.validate_kfx_plugin() is False

    def test_validate_kfx_plugin_unexpected_error(self, format_converter):
        """Test behavior with unexpected errors during plugin check."""
        with patch("subprocess.run", side_effect=Exception("Unexpected error")):
            assert format_converter.validate_kfx_plugin() is False

    def test_validate_kfx_plugin_case_insensitive(self, format_converter):
        """Test that plugin detection is case insensitive."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "kfx output (2, 17, 1) - convert ebooks to kfx format"

        with patch("subprocess.run", return_value=mock_result):
            assert format_converter.validate_kfx_plugin() is True

    def test_validate_kfx_plugin_with_extra_text(self, format_converter):
        """Test plugin detection with extra text in output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
        Some Plugin (1, 0, 0) - Description
        KFX Output (2, 17, 1) - Convert ebooks to KFX format
        Another Plugin (3, 0, 0) - Another description
        """

        with patch("subprocess.run", return_value=mock_result):
            assert format_converter.validate_kfx_plugin() is True


class TestKFXConverterPluginValidation(TestKFXPluginValidation):
    """Test plugin validation in KFXConverter."""

    def test_validate_kfx_plugin_delegates_to_format_converter(self, kfx_converter):
        """Test that KFXConverter uses FormatConverter for plugin validation via system requirements check."""
        # Mock the underlying format converter's plugin validation
        with patch.object(
            kfx_converter._format_converter, "validate_kfx_plugin", return_value=True
        ):
            # Test the system requirements check which includes KFX plugin validation
            requirements = kfx_converter.check_system_requirements()

            # KFX plugin should be available
            assert requirements["kfx_plugin"] is True

    def test_validate_kfx_plugin_handles_exception(self, kfx_converter):
        """Test that KFXConverter handles exceptions during plugin validation."""

        # Mock subprocess.run to return success for calibre tools but fail for plugin check
        def mock_subprocess_run(cmd, **kwargs):
            if cmd == ["calibre", "--version"]:
                return Mock(returncode=0)
            elif cmd == ["ebook-convert", "--version"]:
                return Mock(returncode=0)
            elif cmd == ["calibre-customize", "-l"]:
                raise Exception("Plugin validation error")
            else:
                return Mock(returncode=0)

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            # System requirements should handle the exception gracefully
            requirements = kfx_converter.check_system_requirements()
            assert requirements["kfx_plugin"] is False

    def test_check_system_requirements_includes_kfx_plugin(self, kfx_converter):
        """Test that system requirements check includes KFX plugin status."""
        # Mock the subprocess calls for system requirements
        with patch("subprocess.run") as mock_run:
            # Mock successful calibre and ebook-convert checks
            mock_run.return_value = Mock(
                returncode=0, stdout="KFX Output - Convert ebooks"
            )

            # Mock the KFXConverter specific methods
            with (
                patch.object(
                    kfx_converter, "_check_kindle_previewer", return_value=True
                ),
                patch.object(
                    kfx_converter, "_check_library_access", return_value=False
                ),
            ):
                requirements = kfx_converter.check_system_requirements()

                # Basic requirements
                assert "calibre" in requirements
                assert "ebook-convert" in requirements
                assert "kfx_plugin" in requirements

                # KFX-specific requirements
                assert "kfx_plugin_advanced" in requirements
                assert "kindle_previewer" in requirements
                assert "library_access" in requirements


class TestPluginValidationIntegration(TestKFXPluginValidation):
    """Test plugin validation integration scenarios."""

    def test_plugin_validation_with_real_subprocess_mock(self, format_converter):
        """Test plugin validation with realistic subprocess output."""
        # Simulate realistic calibre-customize -l output
        realistic_output = """
        CSV, EPUB, HTMLZ, LIT, MOBI, ODT, PDB, PDF, RTF, TXT.
        KFX Input (2, 17, 1) - Read Amazon Kindle KFX format files.
        KFX Output (2, 17, 1) - Convert ebooks to KFX format
        Set KFX metadata (2, 17, 1) - Set metadata in KFX files
        """

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = realistic_output

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = format_converter.validate_kfx_plugin()

            assert result is True
            mock_run.assert_called_once_with(
                ["calibre-customize", "-l"], capture_output=True, text=True, timeout=10
            )

    def test_plugin_validation_logs_appropriate_messages(
        self, format_converter, caplog
    ):
        """Test that plugin validation logs appropriate messages."""
        import logging

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "KFX Output (2, 17, 1) - Convert ebooks to KFX format"

        with patch("subprocess.run", return_value=mock_result):
            with caplog.at_level(logging.INFO):
                result = format_converter.validate_kfx_plugin()

                assert result is True
                assert "Validating KFX plugin availability" in caplog.text
                assert "KFX Output plugin found and available" in caplog.text

    def test_plugin_validation_logs_warning_when_not_found(
        self, format_converter, caplog
    ):
        """Test that plugin validation logs warning when plugin not found."""
        import logging

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Some other plugins, but no KFX Output"

        with patch("subprocess.run", return_value=mock_result):
            with caplog.at_level(logging.WARNING):
                result = format_converter.validate_kfx_plugin()

                assert result is False
                assert "KFX Output plugin not found" in caplog.text
                assert "Calibre Preferences → Plugins" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__])
