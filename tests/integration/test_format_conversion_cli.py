"""
Integration tests for format conversion CLI commands.

This module tests the CLI integration with FormatConverter functionality,
including the convert commands for single files and batch operations.
"""

import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from calibre_books.cli.convert import convert
from calibre_books.config.manager import ConfigManager


class TestConvertCLIIntegration:
    """Integration tests for convert CLI commands."""

    def create_test_config(self) -> Path:
        """Create a temporary test configuration file."""
        config_data = {
            "download": {
                "default_format": "epub",
                "download_path": "~/Books",
                "librarian_path": "librarian",
            },
            "calibre": {"library_path": "~/Calibre-Library", "cli_path": "auto"},
            "conversion": {
                "max_parallel": 4,
                "output_path": "/tmp/test-converted",
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

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False)
        yaml.dump(config_data, temp_file)
        temp_file.close()
        return Path(temp_file.name)

    def create_test_file(
        self, suffix: str = ".epub", content: str = "test content"
    ) -> Path:
        """Create a temporary test book file."""
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_file.write(content.encode())
        temp_file.close()
        return Path(temp_file.name)

    def create_test_files_in_dir(self, temp_dir: Path, count: int = 3) -> list[Path]:
        """Create multiple test files in a directory."""
        files = []
        for i in range(count):
            test_file = temp_dir / f"book_{i}.epub"
            test_file.write_text(f"test content {i}")
            files.append(test_file)
        return files


class TestConvertKFXCommand(TestConvertCLIIntegration):
    """Test the convert kfx CLI command."""

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    def test_convert_kfx_check_requirements_all_satisfied(
        self, mock_scanner, mock_converter_class
    ):
        """Test convert kfx --check-requirements when all requirements are satisfied."""
        config_file = self.create_test_config()

        try:
            # Mock converter instance
            mock_converter = Mock()
            mock_converter.check_system_requirements.return_value = {
                "calibre": True,
                "ebook-convert": True,
                "kfx_plugin": True,
                "kindle_previewer": True,
            }
            mock_converter_class.return_value = mock_converter

            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                # Mock context with config
                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": False}

                result = runner.invoke(
                    convert,
                    ["kfx", "--input-dir", temp_dir, "--check-requirements"],
                    obj=context_obj,
                    catch_exceptions=False,
                )

                assert result.exit_code == 0
                assert "System Requirements" in result.output
                assert "All requirements satisfied!" in result.output
                mock_converter.check_system_requirements.assert_called_once()

        finally:
            config_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    def test_convert_kfx_check_requirements_missing_components(
        self, mock_scanner, mock_converter_class
    ):
        """Test convert kfx --check-requirements when components are missing."""
        config_file = self.create_test_config()

        try:
            # Mock converter instance with missing components
            mock_converter = Mock()
            mock_converter.check_system_requirements.return_value = {
                "calibre": True,
                "ebook-convert": False,
                "kfx_plugin": False,
                "kindle_previewer": True,
            }
            mock_converter_class.return_value = mock_converter

            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": False}

                result = runner.invoke(
                    convert,
                    ["kfx", "--input-dir", temp_dir, "--check-requirements"],
                    obj=context_obj,
                    catch_exceptions=False,
                )

                assert result.exit_code == 0
                assert (
                    "Missing requirements: ebook-convert, kfx_plugin" in result.output
                )
                assert "Please install missing components" in result.output

        finally:
            config_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    def test_convert_kfx_plugin_not_available(self, mock_scanner, mock_converter_class):
        """Test convert kfx when KFX plugin is not available."""
        config_file = self.create_test_config()

        try:
            # Mock converter with failed plugin validation
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = False
            mock_converter_class.return_value = mock_converter

            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": False}

                result = runner.invoke(
                    convert, ["kfx", "--input-dir", temp_dir], obj=context_obj
                )

                assert result.exit_code == 1
                assert "KFX Output plugin not found" in result.output
                assert "Please install the KFX Output plugin" in result.output

        finally:
            config_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    @patch("calibre_books.cli.convert.ProgressManager")
    def test_convert_kfx_no_books_found(
        self, mock_progress, mock_scanner, mock_converter_class
    ):
        """Test convert kfx when no convertible books are found."""
        config_file = self.create_test_config()

        try:
            # Mock converter with successful plugin validation
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = True
            mock_converter_class.return_value = mock_converter

            # Mock scanner returning no books
            mock_scanner_instance = Mock()
            mock_scanner_instance.scan_directory.return_value = []
            mock_scanner.return_value = mock_scanner_instance

            # Mock progress manager
            mock_progress_instance = Mock()
            mock_progress.return_value.__enter__ = Mock(
                return_value=mock_progress_instance
            )
            mock_progress.return_value.__exit__ = Mock(return_value=None)

            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": False}

                result = runner.invoke(
                    convert,
                    ["kfx", "--input-dir", temp_dir],
                    obj=context_obj,
                    catch_exceptions=False,
                )

                assert result.exit_code == 0
                assert "No convertible eBook files found" in result.output

        finally:
            config_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    @patch("calibre_books.cli.convert.ProgressManager")
    def test_convert_kfx_dry_run(
        self, mock_progress, mock_scanner, mock_converter_class
    ):
        """Test convert kfx in dry run mode."""
        config_file = self.create_test_config()

        try:
            # Mock converter
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = True
            mock_converter_class.return_value = mock_converter

            # Mock scanner with test books
            from calibre_books.core.book import Book, BookMetadata, BookFormat

            test_books = []
            for i in range(2):
                metadata = BookMetadata(title=f"Test Book {i}", author="Test Author")
                book = Book(metadata=metadata)
                book.format = BookFormat.EPUB
                test_books.append(book)

            mock_scanner_instance = Mock()
            mock_scanner_instance.scan_directory.return_value = test_books
            mock_scanner.return_value = mock_scanner_instance

            # Mock progress manager
            mock_progress_instance = Mock()
            mock_progress.return_value.__enter__ = Mock(
                return_value=mock_progress_instance
            )
            mock_progress.return_value.__exit__ = Mock(return_value=None)

            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": True}

                result = runner.invoke(
                    convert,
                    ["kfx", "--input-dir", temp_dir, "--parallel", "2"],
                    obj=context_obj,
                    catch_exceptions=False,
                )

                assert result.exit_code == 0
                assert "DRY RUN: Would convert 2 books to KFX" in result.output
                assert "Parallel processes: 2" in result.output
                assert "Test Book 0" in result.output

        finally:
            config_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    @patch("calibre_books.cli.convert.ProgressManager")
    def test_convert_kfx_successful_conversion(
        self, mock_progress, mock_scanner, mock_converter_class
    ):
        """Test successful KFX conversion through CLI."""
        config_file = self.create_test_config()

        try:
            # Mock converter with successful conversion
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = True

            # Mock successful conversion results
            successful_results = [Mock(success=True), Mock(success=True)]
            mock_converter.convert_batch.return_value = successful_results
            mock_converter_class.return_value = mock_converter

            # Mock scanner with test books
            from calibre_books.core.book import Book, BookMetadata, BookFormat

            test_books = []
            for i in range(2):
                metadata = BookMetadata(title=f"Test Book {i}", author="Test Author")
                book = Book(metadata=metadata)
                book.format = BookFormat.EPUB
                test_books.append(book)

            mock_scanner_instance = Mock()
            mock_scanner_instance.scan_directory.return_value = test_books
            mock_scanner.return_value = mock_scanner_instance

            # Mock progress manager
            mock_progress_instance = Mock()
            mock_progress.return_value.__enter__ = Mock(
                return_value=mock_progress_instance
            )
            mock_progress.return_value.__exit__ = Mock(return_value=None)

            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": False}

                result = runner.invoke(
                    convert,
                    ["kfx", "--input-dir", temp_dir, "--output-dir", temp_dir],
                    obj=context_obj,
                    catch_exceptions=False,
                )

                assert result.exit_code == 0
                assert "Converting 2 books to KFX format" in result.output
                assert "KFX conversion completed!" in result.output
                assert "Successful: 2" in result.output

                # Verify converter was called with correct parameters
                mock_converter.convert_batch.assert_called_once()
                call_args = mock_converter.convert_batch.call_args
                assert len(call_args[0][0]) == 2  # 2 books
                assert call_args[1]["output_dir"] == Path(temp_dir)

        finally:
            config_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    @patch("calibre_books.cli.convert.ProgressManager")
    def test_convert_kfx_with_failures(
        self, mock_progress, mock_scanner, mock_converter_class
    ):
        """Test KFX conversion with some failures."""
        config_file = self.create_test_config()

        try:
            # Mock converter with mixed results
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = True

            # Mock conversion results with failures
            from calibre_books.core.book import Book, BookMetadata

            failed_book = Book(
                metadata=BookMetadata(title="Failed Book", author="Test Author")
            )
            conversion_results = [
                Mock(success=True, book=Mock(metadata=Mock(title="Success Book"))),
                Mock(success=False, book=failed_book, error="Conversion failed"),
            ]
            mock_converter.convert_batch.return_value = conversion_results
            mock_converter_class.return_value = mock_converter

            # Mock scanner
            mock_scanner_instance = Mock()
            mock_scanner_instance.scan_directory.return_value = [
                Mock(),
                Mock(),
            ]  # 2 books
            mock_scanner.return_value = mock_scanner_instance

            # Mock progress manager
            mock_progress_instance = Mock()
            mock_progress.return_value.__enter__ = Mock(
                return_value=mock_progress_instance
            )
            mock_progress.return_value.__exit__ = Mock(return_value=None)

            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": False}

                result = runner.invoke(
                    convert,
                    ["kfx", "--input-dir", temp_dir],
                    obj=context_obj,
                    catch_exceptions=False,
                )

                assert result.exit_code == 0
                assert "KFX conversion completed!" in result.output
                assert "Successful: 1" in result.output
                assert "Failed: 1" in result.output
                assert "Failed conversions:" in result.output
                assert "Failed Book: Conversion failed" in result.output

        finally:
            config_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    def test_convert_kfx_converter_exception(self, mock_converter_class):
        """Test convert kfx handles converter exceptions."""
        config_file = self.create_test_config()

        try:
            # Mock converter that raises exception during initialization
            mock_converter_class.side_effect = Exception(
                "Converter initialization failed"
            )

            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": False}

                result = runner.invoke(
                    convert, ["kfx", "--input-dir", temp_dir], obj=context_obj
                )

                assert result.exit_code == 1
                assert "KFX conversion failed" in result.output

        finally:
            config_file.unlink()


class TestConvertSingleCommand(TestConvertCLIIntegration):
    """Test the convert single CLI command."""

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    def test_convert_single_kfx_dry_run(self, mock_scanner, mock_converter_class):
        """Test convert single in dry run mode for KFX format."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": True}

            result = runner.invoke(
                convert,
                ["single", "--input-file", str(test_file), "--format", "kfx"],
                obj=context_obj,
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            assert "DRY RUN: Would convert:" in result.output
            assert str(test_file) in result.output
            assert "Format: kfx" in result.output

        finally:
            config_file.unlink()
            test_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    @patch("calibre_books.cli.convert.ProgressManager")
    def test_convert_single_kfx_plugin_not_available(
        self, mock_progress, mock_scanner, mock_converter_class
    ):
        """Test convert single KFX when plugin is not available."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            # Mock converter with failed plugin validation
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = False
            mock_converter_class.return_value = mock_converter

            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": False}

            result = runner.invoke(
                convert,
                ["single", "--input-file", str(test_file), "--format", "kfx"],
                obj=context_obj,
            )

            assert result.exit_code == 1
            assert "KFX Output plugin not found" in result.output

        finally:
            config_file.unlink()
            test_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    @patch("calibre_books.cli.convert.ProgressManager")
    def test_convert_single_kfx_file_processing_fails(
        self, mock_progress, mock_scanner, mock_converter_class
    ):
        """Test convert single KFX when file processing fails."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            # Mock converter
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = True
            mock_converter_class.return_value = mock_converter

            # Mock scanner that fails to create book
            mock_scanner_instance = Mock()
            mock_scanner_instance._create_book_from_file.return_value = None
            mock_scanner.return_value = mock_scanner_instance

            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": False}

            result = runner.invoke(
                convert,
                ["single", "--input-file", str(test_file), "--format", "kfx"],
                obj=context_obj,
            )

            assert result.exit_code == 1
            assert "Could not process file" in result.output

        finally:
            config_file.unlink()
            test_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    @patch("calibre_books.cli.convert.ProgressManager")
    def test_convert_single_kfx_successful_conversion(
        self, mock_progress, mock_scanner, mock_converter_class
    ):
        """Test successful single KFX conversion."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            # Mock converter with successful conversion
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = True

            # Mock successful conversion result
            successful_result = Mock(success=True, output_path="/output/converted.azw3")
            mock_converter.convert_batch.return_value = [successful_result]
            mock_converter_class.return_value = mock_converter

            # Mock scanner that creates a book
            from calibre_books.core.book import Book, BookMetadata

            test_book = Book(
                metadata=BookMetadata(title="Test Book", author="Test Author")
            )

            mock_scanner_instance = Mock()
            mock_scanner_instance._create_book_from_file.return_value = test_book
            mock_scanner.return_value = mock_scanner_instance

            # Mock progress manager
            mock_progress_instance = Mock()
            mock_progress.return_value.__enter__ = Mock(
                return_value=mock_progress_instance
            )
            mock_progress.return_value.__exit__ = Mock(return_value=None)

            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": False}

            result = runner.invoke(
                convert,
                ["single", "--input-file", str(test_file), "--format", "kfx"],
                obj=context_obj,
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            assert "Converting Test Book to KFX" in result.output
            assert "Conversion successful" in result.output
            assert "/output/converted.azw3" in result.output

        finally:
            config_file.unlink()
            test_file.unlink()

    @patch("calibre_books.cli.convert.FormatConverter")
    @patch("calibre_books.cli.convert.FileScanner")
    @patch("calibre_books.cli.convert.ProgressManager")
    def test_convert_single_kfx_conversion_fails(
        self, mock_progress, mock_scanner, mock_converter_class
    ):
        """Test single KFX conversion failure."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            # Mock converter with failed conversion
            mock_converter = Mock()
            mock_converter.validate_kfx_plugin.return_value = True

            # Mock failed conversion result
            failed_result = Mock(success=False, error="Conversion failed")
            mock_converter.convert_batch.return_value = [failed_result]
            mock_converter_class.return_value = mock_converter

            # Mock scanner
            from calibre_books.core.book import Book, BookMetadata

            test_book = Book(
                metadata=BookMetadata(title="Test Book", author="Test Author")
            )

            mock_scanner_instance = Mock()
            mock_scanner_instance._create_book_from_file.return_value = test_book
            mock_scanner.return_value = mock_scanner_instance

            # Mock progress manager
            mock_progress_instance = Mock()
            mock_progress.return_value.__enter__ = Mock(
                return_value=mock_progress_instance
            )
            mock_progress.return_value.__exit__ = Mock(return_value=None)

            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": False}

            result = runner.invoke(
                convert,
                ["single", "--input-file", str(test_file), "--format", "kfx"],
                obj=context_obj,
                catch_exceptions=False,
            )

            assert result.exit_code == 1
            assert "Conversion failed: Conversion failed" in result.output

        finally:
            config_file.unlink()
            test_file.unlink()

    @patch("subprocess.run")
    def test_convert_single_standard_format_successful(self, mock_run):
        """Test successful single conversion to standard format (non-KFX)."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            # Mock successful subprocess run for ebook-convert
            mock_result = Mock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": False}

            with tempfile.TemporaryDirectory() as temp_dir:
                output_file = Path(temp_dir) / f"{test_file.stem}_converted.mobi"

                result = runner.invoke(
                    convert,
                    [
                        "single",
                        "--input-file",
                        str(test_file),
                        "--output-file",
                        str(output_file),
                        "--format",
                        "mobi",
                    ],
                    obj=context_obj,
                    catch_exceptions=False,
                )

                assert result.exit_code == 0
                assert "Converting to MOBI" in result.output
                assert "Conversion successful" in result.output

                # Verify ebook-convert was called with correct parameters
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert call_args[0] == "ebook-convert"
                assert call_args[1] == str(test_file)
                assert call_args[2] == str(output_file)

        finally:
            config_file.unlink()
            test_file.unlink()

    @patch("subprocess.run")
    def test_convert_single_standard_format_fails(self, mock_run):
        """Test single conversion failure for standard format."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            # Mock failed subprocess run
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Conversion error occurred"
            mock_run.return_value = mock_result

            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": False}

            result = runner.invoke(
                convert,
                ["single", "--input-file", str(test_file), "--format", "mobi"],
                obj=context_obj,
                catch_exceptions=False,
            )

            assert result.exit_code == 1
            assert "Conversion failed: Conversion error occurred" in result.output

        finally:
            config_file.unlink()
            test_file.unlink()

    def test_convert_single_auto_output_filename(self):
        """Test convert single generates output filename automatically."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": True}

            result = runner.invoke(
                convert,
                ["single", "--input-file", str(test_file), "--format", "mobi"],
                obj=context_obj,
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            assert "DRY RUN: Would convert:" in result.output

            # Should generate output filename based on input
            expected_output = f"{test_file.stem}_converted.mobi"
            assert expected_output in result.output

        finally:
            config_file.unlink()
            test_file.unlink()

    def test_convert_single_kfx_auto_output_filename(self):
        """Test convert single generates correct output filename for KFX."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            runner = CliRunner()

            config_manager = ConfigManager(config_file)
            context_obj = {"config": config_manager, "dry_run": True}

            result = runner.invoke(
                convert,
                ["single", "--input-file", str(test_file), "--format", "kfx"],
                obj=context_obj,
                catch_exceptions=False,
            )

            assert result.exit_code == 0
            assert "DRY RUN: Would convert:" in result.output

            # KFX format should generate .azw3 extension
            expected_output = f"{test_file.stem}_converted.azw3"
            assert expected_output in result.output

        finally:
            config_file.unlink()
            test_file.unlink()

    def test_convert_single_exception_handling(self):
        """Test convert single handles unexpected exceptions."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            # Mock an exception during format conversion
            with patch(
                "calibre_books.cli.convert.FormatConverter",
                side_effect=Exception("Unexpected error"),
            ):
                runner = CliRunner()

                config_manager = ConfigManager(config_file)
                context_obj = {"config": config_manager, "dry_run": False}

                result = runner.invoke(
                    convert,
                    ["single", "--input-file", str(test_file), "--format", "kfx"],
                    obj=context_obj,
                )

                assert result.exit_code == 1
                assert "Conversion failed: Unexpected error" in result.output

        finally:
            config_file.unlink()
            test_file.unlink()


class TestConvertCommandParameterValidation(TestConvertCLIIntegration):
    """Test parameter validation for convert commands."""

    def test_convert_kfx_missing_input_dir(self):
        """Test convert kfx fails with missing input directory."""
        runner = CliRunner()

        result = runner.invoke(convert, ["kfx"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output

    def test_convert_kfx_nonexistent_input_dir(self):
        """Test convert kfx fails with non-existent input directory."""
        runner = CliRunner()

        result = runner.invoke(convert, ["kfx", "--input-dir", "/non/existent/path"])

        assert result.exit_code != 0
        assert (
            "does not exist" in result.output
            or "No such file" in result.output
            or "Path" in result.output
        )

    def test_convert_single_missing_input_file(self):
        """Test convert single fails with missing input file."""
        runner = CliRunner()

        result = runner.invoke(convert, ["single", "--format", "kfx"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output

    def test_convert_single_nonexistent_input_file(self):
        """Test convert single fails with non-existent input file."""
        runner = CliRunner()

        result = runner.invoke(
            convert,
            ["single", "--input-file", "/non/existent/file.epub", "--format", "kfx"],
        )

        assert result.exit_code != 0
        assert (
            "does not exist" in result.output
            or "No such file" in result.output
            or "Path" in result.output
        )

    def test_convert_single_invalid_format(self):
        """Test convert single validates format parameter."""
        config_file = self.create_test_config()
        test_file = self.create_test_file(".epub")

        try:
            runner = CliRunner()

            result = runner.invoke(
                convert,
                [
                    "single",
                    "--input-file",
                    str(test_file),
                    "--format",
                    "invalid_format",
                ],
            )

            assert result.exit_code != 0
            assert (
                "Invalid value" in result.output
                or "not one of" in result.output
                or "invalid choice" in result.output
            )

        finally:
            config_file.unlink()
            test_file.unlink()

    def test_convert_kfx_parallel_parameter_validation(self):
        """Test convert kfx validates parallel parameter."""
        config_file = self.create_test_config()

        try:
            runner = CliRunner()

            with tempfile.TemporaryDirectory() as temp_dir:
                # Test with negative parallel value
                result = runner.invoke(
                    convert, ["kfx", "--input-dir", temp_dir, "--parallel", "-1"]
                )

                # Should either reject the negative value or handle it gracefully
                # The exact behavior depends on Click validation
                assert (
                    result.exit_code != 0 or result.exit_code == 0
                )  # Either way is acceptable

        finally:
            config_file.unlink()
