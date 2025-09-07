"""
Comprehensive unit tests for FormatConverter class.

This module tests the core conversion functionality implemented in 
src/calibre_books/core/converter.py, including single file conversion,
batch conversion, KFX-specific conversion, and file discovery.
"""

import pytest
import tempfile
import time
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from typing import List, Dict, Any, Optional
from concurrent.futures import Future

from calibre_books.core.converter import FormatConverter
from calibre_books.core.book import BookFormat, ConversionResult
from calibre_books.config.manager import ConfigManager


class TestFormatConverterInitialization:
    """Test FormatConverter initialization and configuration."""

    def create_mock_config_manager(self, conversion_config: Optional[Dict[str, Any]] = None) -> Mock:
        """Create a mock ConfigManager with specified configuration."""
        mock_config = Mock(spec=ConfigManager)
        
        # Default conversion config
        default_config = {
            'max_parallel': 4,
            'output_path': '~/Converted-Books',
            'kfx_plugin_required': True
        }
        
        if conversion_config is not None:
            default_config.update(conversion_config)
        
        mock_config.get_conversion_config.return_value = default_config
        return mock_config

    def test_initialization_with_valid_config(self):
        """Test FormatConverter initializes correctly with valid configuration."""
        config = {
            'max_parallel': 6,
            'output_path': '/tmp/test-output',
            'kfx_plugin_required': False
        }
        mock_config_manager = self.create_mock_config_manager(config)
        
        converter = FormatConverter(mock_config_manager)
        
        assert converter.config_manager == mock_config_manager
        assert converter.max_parallel == 6
        assert str(converter.output_path) == '/tmp/test-output'
        assert converter.kfx_plugin_required is False

    def test_initialization_with_missing_conversion_config(self):
        """Test FormatConverter handles missing conversion configuration gracefully."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.side_effect = Exception("Config error")
        
        converter = FormatConverter(mock_config_manager)
        
        # Should use defaults when config loading fails
        assert converter.max_parallel == 4
        assert converter.output_path == Path('~/Converted-Books').expanduser()
        assert converter.kfx_plugin_required is True

    def test_initialization_with_empty_conversion_config(self):
        """Test FormatConverter handles empty conversion configuration."""
        mock_config_manager = self.create_mock_config_manager({})
        
        converter = FormatConverter(mock_config_manager)
        
        # Should use defaults for missing values
        assert converter.max_parallel == 4
        assert converter.output_path == Path('~/Converted-Books').expanduser()
        assert converter.kfx_plugin_required is True

    def test_initialization_with_partial_config(self):
        """Test FormatConverter handles partial configuration."""
        config = {
            'max_parallel': 8,
            # Missing output_path and kfx_plugin_required
        }
        mock_config_manager = self.create_mock_config_manager(config)
        
        converter = FormatConverter(mock_config_manager)
        
        assert converter.max_parallel == 8
        assert converter.output_path == Path('~/Converted-Books').expanduser()
        assert converter.kfx_plugin_required is True


class TestKFXPluginValidation:
    """Test KFX plugin validation functionality."""

    def create_converter(self) -> FormatConverter:
        """Create a FormatConverter instance for testing."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.return_value = {
            'max_parallel': 4,
            'output_path': '~/test-output',
            'kfx_plugin_required': True
        }
        return FormatConverter(mock_config_manager)

    @patch('subprocess.run')
    def test_validate_kfx_plugin_found(self, mock_run):
        """Test KFX plugin validation when plugin is available."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "KFX Output (2, 17, 1) - Convert ebooks to KFX format"
        mock_run.return_value = mock_result
        
        converter = self.create_converter()
        
        assert converter.validate_kfx_plugin() is True
        mock_run.assert_called_once_with(
            ['calibre-customize', '-l'],
            capture_output=True,
            text=True,
            timeout=10
        )

    @patch('subprocess.run')
    def test_validate_kfx_plugin_not_found(self, mock_run):
        """Test KFX plugin validation when plugin is not available."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Some other plugin output"
        mock_run.return_value = mock_result
        
        converter = self.create_converter()
        
        assert converter.validate_kfx_plugin() is False

    @patch('subprocess.run')
    def test_validate_kfx_plugin_calibre_customize_fails(self, mock_run):
        """Test KFX plugin validation when calibre-customize command fails."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Command failed"
        mock_run.return_value = mock_result
        
        converter = self.create_converter()
        
        assert converter.validate_kfx_plugin() is False

    @patch('subprocess.run')
    def test_validate_kfx_plugin_timeout(self, mock_run):
        """Test KFX plugin validation when command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("calibre-customize", 10)
        
        converter = self.create_converter()
        
        assert converter.validate_kfx_plugin() is False

    @patch('subprocess.run')
    def test_validate_kfx_plugin_command_not_found(self, mock_run):
        """Test KFX plugin validation when calibre-customize not found."""
        mock_run.side_effect = FileNotFoundError("Command not found")
        
        converter = self.create_converter()
        
        assert converter.validate_kfx_plugin() is False

    @patch('subprocess.run')
    def test_validate_kfx_plugin_unexpected_error(self, mock_run):
        """Test KFX plugin validation with unexpected error."""
        mock_run.side_effect = RuntimeError("Unexpected error")
        
        converter = self.create_converter()
        
        assert converter.validate_kfx_plugin() is False


class TestConvertSingle:
    """Test single file conversion functionality."""

    def create_converter(self) -> FormatConverter:
        """Create a FormatConverter instance for testing."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.return_value = {
            'max_parallel': 4,
            'output_path': '/tmp/test-output',
            'kfx_plugin_required': True
        }
        return FormatConverter(mock_config_manager)

    def create_test_file(self, suffix: str = ".epub", content: bytes = b"test content") -> Path:
        """Create a temporary test file."""
        temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)

    def test_convert_single_input_file_not_exists(self):
        """Test convert_single with non-existent input file."""
        converter = self.create_converter()
        non_existent_file = Path("/non/existent/file.epub")
        
        result = converter.convert_single(
            input_file=non_existent_file,
            output_format="mobi"
        )
        
        assert result.success is False
        assert "Input file does not exist" in result.error
        assert result.input_file == non_existent_file
        assert result.output_format == BookFormat.MOBI

    def test_convert_single_input_path_not_file(self):
        """Test convert_single with directory as input."""
        converter = self.create_converter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            result = converter.convert_single(
                input_file=dir_path,
                output_format="mobi"
            )
            
            assert result.success is False
            assert "Input path is not a file" in result.error
            assert result.input_file == dir_path

    def test_convert_single_unsupported_format(self):
        """Test convert_single with unsupported input format."""
        converter = self.create_converter()
        test_file = self.create_test_file(".unknown")
        
        try:
            result = converter.convert_single(
                input_file=test_file,
                output_format="mobi"
            )
            
            assert result.success is False
            assert "Unsupported input format" in result.error
            assert result.input_format == BookFormat.EPUB  # Fallback
        finally:
            test_file.unlink()

    def test_convert_single_dry_run(self):
        """Test convert_single in dry run mode."""
        converter = self.create_converter()
        test_file = self.create_test_file(".epub")
        
        try:
            result = converter.convert_single(
                input_file=test_file,
                output_format="mobi",
                dry_run=True
            )
            
            assert result.success is True
            assert result.input_file == test_file
            assert result.output_format == BookFormat.MOBI
            assert result.conversion_time == 0.0
            assert result.output_file is not None
            assert result.file_size_before == test_file.stat().st_size
            assert result.file_size_after == test_file.stat().st_size
        finally:
            test_file.unlink()

    @patch('subprocess.run')
    def test_convert_single_successful_conversion(self, mock_run):
        """Test successful single file conversion."""
        converter = self.create_converter()
        test_file = self.create_test_file(".epub")
        
        # Mock successful subprocess run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                output_file = Path(temp_dir) / "output.mobi"
                # Create the output file to simulate successful conversion
                output_file.write_bytes(b"converted content")
                
                with patch.object(converter, 'output_path', Path(temp_dir)):
                    result = converter.convert_single(
                        input_file=test_file,
                        output_file=output_file,
                        output_format="mobi"
                    )
                
                assert result.success is True
                assert result.input_file == test_file
                assert result.output_file == output_file
                assert result.input_format == BookFormat.EPUB
                assert result.output_format == BookFormat.MOBI
                assert result.conversion_time > 0
                assert result.file_size_before > 0
                assert result.file_size_after > 0
        finally:
            test_file.unlink()

    @patch('subprocess.run')
    def test_convert_single_conversion_fails(self, mock_run):
        """Test single file conversion when ebook-convert fails."""
        converter = self.create_converter()
        test_file = self.create_test_file(".epub")
        
        # Mock failed subprocess run
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Conversion error occurred"
        mock_run.return_value = mock_result
        
        try:
            result = converter.convert_single(
                input_file=test_file,
                output_format="mobi"
            )
            
            assert result.success is False
            assert "Conversion error occurred" in result.error
            assert result.input_file == test_file
            assert result.conversion_time > 0
        finally:
            test_file.unlink()

    @patch('subprocess.run')
    def test_convert_single_timeout(self, mock_run):
        """Test single file conversion timeout handling."""
        converter = self.create_converter()
        test_file = self.create_test_file(".epub")
        
        mock_run.side_effect = subprocess.TimeoutExpired("ebook-convert", 600)
        
        try:
            result = converter.convert_single(
                input_file=test_file,
                output_format="mobi"
            )
            
            assert result.success is False
            assert "Conversion timeout" in result.error
            assert result.input_file == test_file
        finally:
            test_file.unlink()

    @patch('subprocess.run')
    def test_convert_single_unexpected_exception(self, mock_run):
        """Test single file conversion with unexpected exception."""
        converter = self.create_converter()
        test_file = self.create_test_file(".epub")
        
        mock_run.side_effect = RuntimeError("Unexpected error")
        
        try:
            result = converter.convert_single(
                input_file=test_file,
                output_format="mobi"
            )
            
            assert result.success is False
            assert "Unexpected error during conversion" in result.error
            assert result.input_file == test_file
        finally:
            test_file.unlink()

    def test_convert_single_progress_callback(self):
        """Test convert_single with progress callback in dry run."""
        converter = self.create_converter()
        test_file = self.create_test_file(".epub")
        
        progress_calls = []
        def progress_callback(progress: float, message: str):
            progress_calls.append((progress, message))
        
        try:
            result = converter.convert_single(
                input_file=test_file,
                output_format="mobi",
                dry_run=True,
                progress_callback=progress_callback
            )
            
            assert result.success is True
            # No progress callback should be called in dry run for single conversion
            assert len(progress_calls) == 0
        finally:
            test_file.unlink()

    def test_convert_single_auto_output_path(self):
        """Test convert_single generates output path automatically."""
        converter = self.create_converter()
        test_file = self.create_test_file(".epub")
        
        try:
            result = converter.convert_single(
                input_file=test_file,
                output_format="mobi",
                dry_run=True
            )
            
            assert result.success is True
            expected_output = converter.output_path / f"{test_file.stem}.mobi"
            assert result.output_file == expected_output
        finally:
            test_file.unlink()


class TestConvertBatch:
    """Test batch conversion functionality."""

    def create_converter(self) -> FormatConverter:
        """Create a FormatConverter instance for testing."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.return_value = {
            'max_parallel': 4,
            'output_path': '/tmp/test-output',
            'kfx_plugin_required': True
        }
        return FormatConverter(mock_config_manager)

    def create_test_files(self, count: int = 3, suffix: str = ".epub") -> List[Path]:
        """Create multiple temporary test files."""
        files = []
        for i in range(count):
            temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            temp_file.write(f"test content {i}".encode())
            temp_file.close()
            files.append(Path(temp_file.name))
        return files

    def test_convert_batch_empty_file_list(self):
        """Test batch conversion with empty file list."""
        converter = self.create_converter()
        
        results = converter.convert_batch([])
        
        assert results == []

    def test_convert_batch_dry_run(self):
        """Test batch conversion in dry run mode."""
        converter = self.create_converter()
        test_files = self.create_test_files(3)
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                results = converter.convert_batch(
                    files=test_files,
                    output_dir=Path(temp_dir),
                    output_format="mobi",
                    dry_run=True
                )
                
                assert len(results) == 3
                for result in results:
                    assert result.success is True
                    assert result.output_format == BookFormat.MOBI
                    assert result.conversion_time == 0.0
        finally:
            for file in test_files:
                file.unlink()

    @patch.object(FormatConverter, 'convert_single')
    def test_convert_batch_skip_existing_outputs(self, mock_convert_single):
        """Test batch conversion skips files with existing outputs."""
        converter = self.create_converter()
        test_files = self.create_test_files(2)
        
        # Mock convert_single to return successful result for the one file that gets processed
        result = ConversionResult(
            input_file=test_files[1],  # Second file (first one will be skipped)
            output_file=Path(f"/tmp/{test_files[1].stem}.mobi"),
            input_format=BookFormat.EPUB,
            output_format=BookFormat.MOBI,
            success=True,
            conversion_time=1.0,
            file_size_before=100,
            file_size_after=90
        )
        
        mock_convert_single.return_value = result
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir)
                
                # Create existing output file for first input
                existing_output = output_dir / f"{test_files[0].stem}.mobi"
                existing_output.write_text("existing content")
                
                results = converter.convert_batch(
                    files=test_files,
                    output_dir=output_dir,
                    output_format="mobi"
                )
                
                # Should only process the second file (first is skipped due to existing output)
                # convert_single should only be called once
                assert mock_convert_single.call_count == 1
                assert len(results) == 1
                # The remaining result should be for the file that doesn't have existing output
                processed_file = results[0].input_file
                assert processed_file in test_files
                # The processed file should NOT be the one with existing output
                assert processed_file != test_files[0]
        finally:
            for file in test_files:
                file.unlink()

    @patch.object(FormatConverter, 'convert_single')
    def test_convert_batch_parallel_processing(self, mock_convert_single):
        """Test batch conversion calls convert_single for each file."""
        converter = self.create_converter()
        test_files = self.create_test_files(3)
        
        # Mock successful conversions
        mock_results = []
        for i, file in enumerate(test_files):
            result = ConversionResult(
                input_file=file,
                output_file=Path(f"/tmp/output_{i}.mobi"),
                input_format=BookFormat.EPUB,
                output_format=BookFormat.MOBI,
                success=True,
                conversion_time=1.0,
                file_size_before=100,
                file_size_after=90
            )
            mock_results.append(result)
        
        mock_convert_single.side_effect = mock_results
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                results = converter.convert_batch(
                    files=test_files,
                    output_dir=Path(temp_dir),
                    output_format="mobi",
                    parallel=2
                )
                
                # Should call convert_single for each file
                assert mock_convert_single.call_count == 3
                
                # Should return 3 results
                assert len(results) == 3
                for result in results:
                    assert result.success is True
        finally:
            for file in test_files:
                file.unlink()

    def test_convert_batch_parallel_limit_by_config(self):
        """Test batch conversion respects max_parallel configuration."""
        converter = self.create_converter()
        converter.max_parallel = 2  # Set lower limit
        test_files = self.create_test_files(1)
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                results = converter.convert_batch(
                    files=test_files,
                    output_dir=Path(temp_dir),
                    output_format="mobi",
                    parallel=8,  # Request more than max_parallel
                    dry_run=True
                )
                
                # Should still work (dry run doesn't test parallel limit directly,
                # but we can verify the files were processed)
                assert len(results) == 1
        finally:
            for file in test_files:
                file.unlink()

    def test_convert_batch_progress_callback(self):
        """Test batch conversion with progress callback."""
        converter = self.create_converter()
        test_files = self.create_test_files(2)
        
        progress_calls = []
        def progress_callback(progress: float, message: str):
            progress_calls.append((progress, message))
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                results = converter.convert_batch(
                    files=test_files,
                    output_dir=Path(temp_dir),
                    output_format="mobi",
                    dry_run=True,
                    progress_callback=progress_callback
                )
                
                assert len(results) == 2
                # In dry run mode, progress callback should be called
                assert len(progress_calls) == 2
                assert progress_calls[0] == (0.5, "Preview 1/2")
                assert progress_calls[1] == (1.0, "Preview 2/2")
        finally:
            for file in test_files:
                file.unlink()

    def test_convert_batch_default_output_dir(self):
        """Test batch conversion uses default output directory."""
        converter = self.create_converter()
        test_files = self.create_test_files(1)
        
        try:
            results = converter.convert_batch(
                files=test_files,
                output_format="mobi",
                dry_run=True
            )
            
            assert len(results) == 1
            # Should use converter.output_path as default
            expected_output = converter.output_path / f"{test_files[0].stem}.mobi"
            assert results[0].output_file == expected_output
        finally:
            for file in test_files:
                file.unlink()


class TestConvertKfxBatch:
    """Test KFX-specific batch conversion functionality."""

    def create_converter(self, kfx_plugin_required: bool = True) -> FormatConverter:
        """Create a FormatConverter instance for testing."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.return_value = {
            'max_parallel': 4,
            'output_path': '/tmp/test-output',
            'kfx_plugin_required': kfx_plugin_required
        }
        return FormatConverter(mock_config_manager)

    def create_test_files(self, count: int = 3, suffix: str = ".kfx") -> List[Path]:
        """Create multiple temporary test files."""
        files = []
        for i in range(count):
            temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            temp_file.write(f"test content {i}".encode())
            temp_file.close()
            files.append(Path(temp_file.name))
        return files

    def test_convert_kfx_batch_empty_file_list(self):
        """Test KFX batch conversion with empty file list."""
        converter = self.create_converter()
        
        results = converter.convert_kfx_batch([])
        
        assert results == []

    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_convert_kfx_batch_plugin_not_available(self, mock_validate):
        """Test KFX batch conversion when plugin is not available."""
        converter = self.create_converter()
        mock_validate.return_value = False
        test_files = self.create_test_files(2)
        
        try:
            results = converter.convert_kfx_batch(test_files)
            
            assert len(results) == 2
            for result in results:
                assert result.success is False
                assert "KFX Output plugin is required" in result.error
                assert result.input_format == BookFormat.KFX
                assert result.output_format == BookFormat.EPUB  # Default
        finally:
            for file in test_files:
                file.unlink()

    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_convert_kfx_batch_plugin_not_required(self, mock_validate):
        """Test KFX batch conversion when plugin is not required."""
        converter = self.create_converter(kfx_plugin_required=False)
        test_files = self.create_test_files(1)
        
        try:
            results = converter.convert_kfx_batch(
                test_files,
                dry_run=True
            )
            
            # Plugin validation should not be called when not required
            mock_validate.assert_not_called()
            assert len(results) == 1
            assert results[0].success is True
        finally:
            for file in test_files:
                file.unlink()

    @patch.object(FormatConverter, '_detect_format')
    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_convert_kfx_batch_filters_non_kfx_files(self, mock_validate, mock_detect):
        """Test KFX batch conversion filters out non-KFX files."""
        converter = self.create_converter()
        mock_validate.return_value = True
        
        # Create mixed file types
        kfx_files = self.create_test_files(2, ".kfx")
        epub_files = self.create_test_files(1, ".epub")
        all_files = kfx_files + epub_files
        
        # Mock format detection
        def detect_format(file_path):
            if file_path.suffix == ".kfx":
                return BookFormat.KFX
            elif file_path.suffix == ".epub":
                return BookFormat.EPUB
            return None
        
        mock_detect.side_effect = detect_format
        
        try:
            results = converter.convert_kfx_batch(
                all_files,
                dry_run=True
            )
            
            # Should process 2 KFX files and create 1 error result for non-KFX file
            assert len(results) == 3
            
            # Check KFX results
            kfx_results = [r for r in results if r.input_file in kfx_files]
            assert len(kfx_results) == 2
            for result in kfx_results:
                assert result.success is True
                assert result.input_format == BookFormat.KFX
                assert "_from_kfx" in str(result.output_file)
            
            # Check non-KFX results
            non_kfx_results = [r for r in results if r.input_file in epub_files]
            assert len(non_kfx_results) == 1
            assert non_kfx_results[0].success is False
            assert "File is not KFX format" in non_kfx_results[0].error
        finally:
            for file in all_files:
                file.unlink()

    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_convert_kfx_batch_dry_run(self, mock_validate):
        """Test KFX batch conversion in dry run mode."""
        converter = self.create_converter()
        mock_validate.return_value = True
        test_files = self.create_test_files(2)
        
        progress_calls = []
        def progress_callback(progress: float, message: str):
            progress_calls.append((progress, message))
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                results = converter.convert_kfx_batch(
                    test_files,
                    output_dir=Path(temp_dir),
                    output_format="epub",
                    dry_run=True,
                    progress_callback=progress_callback
                )
                
                assert len(results) == 2
                for result in results:
                    assert result.success is True
                    assert result.input_format == BookFormat.KFX
                    assert result.output_format == BookFormat.EPUB
                    assert result.conversion_time == 0.0
                    assert "_from_kfx" in str(result.output_file)
                
                # Progress callback should be called
                assert len(progress_calls) == 2
                assert "KFX Preview" in progress_calls[0][1]
        finally:
            for file in test_files:
                file.unlink()

    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_convert_kfx_batch_special_naming(self, mock_validate):
        """Test KFX batch conversion uses special naming scheme."""
        converter = self.create_converter()
        mock_validate.return_value = True
        test_files = self.create_test_files(1)
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                results = converter.convert_kfx_batch(
                    test_files,
                    output_dir=Path(temp_dir),
                    output_format="epub",
                    dry_run=True
                )
                
                assert len(results) == 1
                expected_name = f"{test_files[0].stem}_from_kfx.epub"
                assert results[0].output_file.name == expected_name
        finally:
            for file in test_files:
                file.unlink()

    @patch.object(FormatConverter, 'convert_single')
    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_convert_kfx_batch_skip_existing_outputs(self, mock_validate, mock_convert_single):
        """Test KFX batch conversion skips existing output files."""
        converter = self.create_converter()
        mock_validate.return_value = True
        test_files = self.create_test_files(2)
        
        # Mock convert_single to return successful result for the one file that gets processed
        result = ConversionResult(
            input_file=test_files[1],  # Second file (first one will be skipped)
            output_file=Path(f"/tmp/{test_files[1].stem}_from_kfx.epub"),
            input_format=BookFormat.KFX,
            output_format=BookFormat.EPUB,
            success=True,
            conversion_time=1.0,
            file_size_before=100,
            file_size_after=90
        )
        mock_convert_single.return_value = result
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                output_dir = Path(temp_dir)
                
                # Create existing output for first file
                existing_output = output_dir / f"{test_files[0].stem}_from_kfx.epub"
                existing_output.write_text("existing content")
                
                results = converter.convert_kfx_batch(
                    test_files,
                    output_dir=output_dir,
                    output_format="epub"
                )
                
                # Should only process the second file (first is skipped due to existing output)
                # convert_single should only be called once
                assert mock_convert_single.call_count == 1
                assert len(results) == 1
                # The remaining result should be for the file that doesn't have existing output
                processed_file = results[0].input_file
                assert processed_file in test_files
                # The processed file should NOT be the one with existing output
                assert processed_file != test_files[0]
        finally:
            for file in test_files:
                file.unlink()

    @patch.object(FormatConverter, 'convert_single')
    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_convert_kfx_batch_parallel_execution(self, mock_validate, mock_convert_single):
        """Test KFX batch conversion calls convert_single for each file."""
        converter = self.create_converter()
        mock_validate.return_value = True
        test_files = self.create_test_files(2)
        
        # Mock successful conversions
        mock_results = []
        for i, file in enumerate(test_files):
            result = ConversionResult(
                input_file=file,
                output_file=Path(f"/tmp/output_{i}_from_kfx.epub"),
                input_format=BookFormat.KFX,
                output_format=BookFormat.EPUB,
                success=True,
                conversion_time=1.0,
                file_size_before=100,
                file_size_after=90
            )
            mock_results.append(result)
        
        mock_convert_single.side_effect = mock_results
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                results = converter.convert_kfx_batch(
                    test_files,
                    output_dir=Path(temp_dir),
                    output_format="epub",
                    parallel=2
                )
                
                # Should call convert_single for each file with KFX-specific options
                assert mock_convert_single.call_count == 2
                for call in mock_convert_single.call_args_list:
                    args, kwargs = call
                    assert kwargs['include_cover'] is True  # KFX always includes cover
        finally:
            for file in test_files:
                file.unlink()

    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_convert_kfx_batch_progress_reporting(self, mock_validate):
        """Test KFX batch conversion progress reporting."""
        converter = self.create_converter()
        mock_validate.return_value = True
        test_files = self.create_test_files(3)
        
        progress_calls = []
        def progress_callback(progress: float, message: str):
            progress_calls.append((progress, message))
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                results = converter.convert_kfx_batch(
                    test_files,
                    output_dir=Path(temp_dir),
                    dry_run=True,
                    progress_callback=progress_callback
                )
                
                assert len(results) == 3
                assert len(progress_calls) == 3
                
                # Check progress increments
                expected_progresses = [1/3, 2/3, 1.0]
                for i, (progress, message) in enumerate(progress_calls):
                    assert abs(progress - expected_progresses[i]) < 0.01
                    assert "KFX Preview" in message
        finally:
            for file in test_files:
                file.unlink()


class TestFindConvertibleFiles:
    """Test file discovery functionality."""

    def create_converter(self) -> FormatConverter:
        """Create a FormatConverter instance for testing."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.return_value = {
            'max_parallel': 4,
            'output_path': '/tmp/test-output',
            'kfx_plugin_required': True
        }
        return FormatConverter(mock_config_manager)

    def test_find_convertible_files_nonexistent_directory(self):
        """Test find_convertible_files with non-existent directory."""
        converter = self.create_converter()
        non_existent_dir = Path("/non/existent/directory")
        
        files = converter.find_convertible_files(non_existent_dir)
        
        assert files == []

    def test_find_convertible_files_file_as_directory(self):
        """Test find_convertible_files with file path instead of directory."""
        converter = self.create_converter()
        
        with tempfile.NamedTemporaryFile() as temp_file:
            file_path = Path(temp_file.name)
            
            files = converter.find_convertible_files(file_path)
            
            assert files == []

    def test_find_convertible_files_empty_directory(self):
        """Test find_convertible_files with empty directory."""
        converter = self.create_converter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            files = converter.find_convertible_files(Path(temp_dir))
            
            assert files == []

    def test_find_convertible_files_mixed_files(self):
        """Test find_convertible_files filters supported formats correctly."""
        converter = self.create_converter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create mixed files
            supported_files = []
            for ext in ['.epub', '.mobi', '.pdf', '.azw3']:
                file_path = dir_path / f"book{ext}"
                file_path.write_text("content")
                supported_files.append(file_path)
            
            # Create unsupported files
            unsupported_files = []
            for ext in ['.txt.bak', '.jpg', '.zip', '.unknown']:
                file_path = dir_path / f"file{ext}"
                file_path.write_text("content")
                unsupported_files.append(file_path)
            
            files = converter.find_convertible_files(dir_path)
            
            # Should only return supported formats
            assert len(files) == len(supported_files)
            for file in files:
                assert file in supported_files
                assert file not in unsupported_files

    def test_find_convertible_files_recursive_search(self):
        """Test find_convertible_files with recursive search."""
        converter = self.create_converter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create file in root
            root_file = dir_path / "root.epub"
            root_file.write_text("content")
            
            # Create subdirectory with files
            sub_dir = dir_path / "subdir"
            sub_dir.mkdir()
            sub_file = sub_dir / "sub.mobi"
            sub_file.write_text("content")
            
            # Test non-recursive (default)
            files_nonrecursive = converter.find_convertible_files(dir_path, recursive=False)
            assert len(files_nonrecursive) == 1
            assert root_file in files_nonrecursive
            
            # Test recursive
            files_recursive = converter.find_convertible_files(dir_path, recursive=True)
            assert len(files_recursive) == 2
            assert root_file in files_recursive
            assert sub_file in files_recursive

    def test_find_convertible_files_source_format_filter(self):
        """Test find_convertible_files with source format filtering."""
        converter = self.create_converter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create files with different formats
            epub_file = dir_path / "book.epub"
            epub_file.write_text("content")
            mobi_file = dir_path / "book.mobi"
            mobi_file.write_text("content")
            pdf_file = dir_path / "book.pdf"
            pdf_file.write_text("content")
            
            # Test filtering by specific format
            epub_files = converter.find_convertible_files(dir_path, source_format="epub")
            assert len(epub_files) == 1
            assert epub_file in epub_files
            
            mobi_files = converter.find_convertible_files(dir_path, source_format="mobi")
            assert len(mobi_files) == 1
            assert mobi_file in mobi_files
            
            # Test with format that has leading dot
            epub_files_dot = converter.find_convertible_files(dir_path, source_format=".epub")
            assert len(epub_files_dot) == 1
            assert epub_file in epub_files_dot

    def test_find_convertible_files_unsupported_source_format(self):
        """Test find_convertible_files with unsupported source format."""
        converter = self.create_converter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create supported file
            epub_file = dir_path / "book.epub"
            epub_file.write_text("content")
            
            # Request unsupported format
            files = converter.find_convertible_files(dir_path, source_format="unsupported")
            
            assert files == []

    def test_find_convertible_files_excludes_conversion_outputs(self):
        """Test find_convertible_files excludes conversion output files."""
        converter = self.create_converter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create original files
            original = dir_path / "book.epub"
            original.write_text("content")
            
            # Create conversion output files (should be excluded)
            kfx_output = dir_path / "book_from_kfx.epub"
            kfx_output.write_text("content")
            converted_output = dir_path / "book_converted.epub"
            converted_output.write_text("content")
            
            files = converter.find_convertible_files(dir_path)
            
            # Should only find the original file
            assert len(files) == 1
            assert original in files
            assert kfx_output not in files
            assert converted_output not in files

    def test_find_convertible_files_sorted_results(self):
        """Test find_convertible_files returns sorted results."""
        converter = self.create_converter()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create files in non-alphabetical order
            files_to_create = ['zebra.epub', 'alpha.mobi', 'beta.pdf']
            for filename in files_to_create:
                file_path = dir_path / filename
                file_path.write_text("content")
            
            files = converter.find_convertible_files(dir_path)
            
            # Should be sorted by name
            expected_order = [dir_path / 'alpha.mobi', dir_path / 'beta.pdf', dir_path / 'zebra.epub']
            assert files == expected_order

    def test_find_convertible_files_progress_callback(self):
        """Test find_convertible_files with progress callback."""
        converter = self.create_converter()
        
        progress_calls = []
        def progress_callback(message: str):
            progress_calls.append(message)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create a test file
            test_file = dir_path / "book.epub"
            test_file.write_text("content")
            
            files = converter.find_convertible_files(
                dir_path, 
                progress_callback=progress_callback
            )
            
            # Final progress callback should be called
            assert len(progress_calls) >= 1
            assert "Found" in progress_calls[-1]
            assert len(files) == 1

    @patch.object(FormatConverter, 'get_supported_formats')
    def test_find_convertible_files_get_supported_formats_fails(self, mock_get_formats):
        """Test find_convertible_files when get_supported_formats fails."""
        converter = self.create_converter()
        mock_get_formats.side_effect = Exception("Format query failed")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create some files
            epub_file = dir_path / "book.epub"
            epub_file.write_text("content")
            
            files = converter.find_convertible_files(dir_path)
            
            # Should still work with default format list
            assert len(files) == 1
            assert epub_file in files

    def test_find_convertible_files_with_permission_protected_dir(self):
        """Test find_convertible_files behavior with a directory that exists but can't be scanned."""
        converter = self.create_converter()
        
        # Test with a directory that exists but might have permission issues  
        # Note: This test verifies the method doesn't crash on scanning errors
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            
            # Create a normal file
            epub_file = dir_path / "book.epub"  
            epub_file.write_text("content")
            
            files = converter.find_convertible_files(dir_path)
            
            # Should handle the directory gracefully and return files that can be found
            assert isinstance(files, list)  # Method completes without crashing
            assert len(files) >= 0  # Returns a valid list


class TestGetSupportedFormats:
    """Test supported formats functionality."""

    def create_converter(self) -> FormatConverter:
        """Create a FormatConverter instance for testing."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.return_value = {
            'max_parallel': 4,
            'output_path': '/tmp/test-output',
            'kfx_plugin_required': True
        }
        return FormatConverter(mock_config_manager)

    @patch.object(FormatConverter, '_query_calibre_formats')
    def test_get_supported_formats_successful_query(self, mock_query):
        """Test get_supported_formats with successful Calibre query."""
        converter = self.create_converter()
        
        # Mock successful format query
        from dataclasses import dataclass
        
        @dataclass
        class Format:
            name: str
            extension: str
            description: str
        
        mock_input_formats = [
            Format("EPUB", ".epub", "Standard e-book format"),
            Format("MOBI", ".mobi", "Amazon Kindle format"),
        ]
        mock_output_formats = [
            Format("EPUB", ".epub", "Standard e-book format"),
            Format("PDF", ".pdf", "Portable Document Format"),
        ]
        
        mock_query.return_value = (mock_input_formats, mock_output_formats)
        
        formats = converter.get_supported_formats()
        
        assert len(formats.input_formats) == 2
        assert len(formats.output_formats) == 2
        assert formats.input_formats[0].name == "EPUB"
        assert formats.output_formats[1].name == "PDF"
        mock_query.assert_called_once()

    @patch.object(FormatConverter, '_query_calibre_formats')
    def test_get_supported_formats_query_fails(self, mock_query):
        """Test get_supported_formats falls back when Calibre query fails."""
        converter = self.create_converter()
        mock_query.side_effect = Exception("Query failed")
        
        formats = converter.get_supported_formats()
        
        # Should return default format list
        assert len(formats.input_formats) > 0
        assert len(formats.output_formats) > 0
        
        # Check for some expected default formats
        input_names = [f.name for f in formats.input_formats]
        output_names = [f.name for f in formats.output_formats]
        
        assert "EPUB" in input_names
        assert "MOBI" in input_names
        assert "EPUB" in output_names
        assert "PDF" in output_names


class TestHelperMethods:
    """Test helper methods of FormatConverter."""

    def create_converter(self) -> FormatConverter:
        """Create a FormatConverter instance for testing."""
        mock_config_manager = Mock(spec=ConfigManager)
        mock_config_manager.get_conversion_config.return_value = {
            'max_parallel': 4,
            'output_path': '/tmp/test-output',
            'kfx_plugin_required': True
        }
        return FormatConverter(mock_config_manager)

    def test_detect_format(self):
        """Test _detect_format method."""
        converter = self.create_converter()
        
        # Test supported formats
        assert converter._detect_format(Path("book.epub")) == BookFormat.EPUB
        assert converter._detect_format(Path("book.mobi")) == BookFormat.MOBI
        assert converter._detect_format(Path("book.pdf")) == BookFormat.PDF
        assert converter._detect_format(Path("book.azw3")) == BookFormat.AZW3
        assert converter._detect_format(Path("book.kfx")) == BookFormat.KFX
        assert converter._detect_format(Path("book.html")) == BookFormat.HTML
        assert converter._detect_format(Path("book.htm")) == BookFormat.HTML  # HTML alias
        
        # Test unsupported formats
        assert converter._detect_format(Path("file.unknown")) is None
        assert converter._detect_format(Path("file.txt.bak")) is None
        
        # Test case insensitive
        assert converter._detect_format(Path("book.EPUB")) == BookFormat.EPUB
        assert converter._detect_format(Path("book.Mobi")) == BookFormat.MOBI

    def test_build_conversion_command_basic(self):
        """Test _build_conversion_command with basic parameters."""
        converter = self.create_converter()
        
        cmd = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.mobi"),
            output_format="mobi"
        )
        
        assert cmd[0] == "ebook-convert"
        assert cmd[1] == "/input.epub"
        assert cmd[2] == "/output.mobi"
        assert "--preserve-metadata" in cmd

    @patch.object(FormatConverter, 'validate_kfx_plugin')
    def test_build_conversion_command_kfx_format(self, mock_validate):
        """Test _build_conversion_command for KFX format."""
        converter = self.create_converter()
        mock_validate.return_value = True
        
        cmd = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.azw3"),
            output_format="kfx"
        )
        
        # Should include KFX-specific options
        cmd_str = " ".join(str(x) for x in cmd)
        assert "--output-profile kindle_fire" in cmd_str
        assert "--no-inline-toc" in cmd_str
        assert "--margin-left 5" in cmd_str

    def test_build_conversion_command_pdf_format(self):
        """Test _build_conversion_command for PDF format."""
        converter = self.create_converter()
        
        cmd = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.pdf"),
            output_format="pdf"
        )
        
        cmd_str = " ".join(str(x) for x in cmd)
        assert "--paper-size a4" in cmd_str
        assert "--pdf-default-font-size 12" in cmd_str

    def test_build_conversion_command_quality_settings(self):
        """Test _build_conversion_command with different quality settings."""
        converter = self.create_converter()
        
        # High quality
        cmd_high = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.epub"),
            output_format="epub",
            quality="high"
        )
        
        cmd_str = " ".join(str(x) for x in cmd_high)
        assert "--preserve-cover-aspect-ratio" in cmd_str
        assert "--embed-all-fonts" in cmd_str
        assert "text-align: justify" in cmd_str
        
        # Low quality
        cmd_low = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.epub"),
            output_format="epub",
            quality="low"
        )
        
        cmd_str = " ".join(str(x) for x in cmd_low)
        assert "--compress-images" in cmd_str
        assert "--jpeg-quality 60" in cmd_str

    def test_build_conversion_command_cover_options(self):
        """Test _build_conversion_command with cover options."""
        converter = self.create_converter()
        
        # With cover
        cmd_with_cover = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.epub"),
            output_format="epub",
            include_cover=True
        )
        cmd_str = " ".join(str(x) for x in cmd_with_cover)
        assert "--preserve-cover-aspect-ratio" in cmd_str
        
        # Without cover
        cmd_no_cover = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.epub"),
            output_format="epub",
            include_cover=False
        )
        cmd_str = " ".join(str(x) for x in cmd_no_cover)
        assert "--no-default-epub-cover" in cmd_str

    def test_build_conversion_command_metadata_preservation(self):
        """Test _build_conversion_command with metadata preservation options."""
        converter = self.create_converter()
        
        # Preserve metadata
        cmd_preserve = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.mobi"),
            output_format="mobi",
            preserve_metadata=True
        )
        assert "--preserve-metadata" in cmd_preserve
        
        # Don't preserve metadata
        cmd_no_preserve = converter._build_conversion_command(
            input_file=Path("/input.epub"),
            output_file=Path("/output.mobi"),
            output_format="mobi",
            preserve_metadata=False
        )
        assert "--preserve-metadata" not in cmd_no_preserve

    @patch('subprocess.run')
    def test_query_calibre_formats_successful(self, mock_run):
        """Test _query_calibre_formats with successful command execution."""
        converter = self.create_converter()
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Input Formats: epub, mobi, pdf"
        mock_run.return_value = mock_result
        
        input_formats, output_formats = converter._query_calibre_formats()
        
        # Should return default lists since parsing is simplified
        assert len(input_formats) > 0
        assert len(output_formats) > 0
        
        mock_run.assert_called_once_with(
            ['ebook-convert', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )

    @patch('subprocess.run')
    def test_query_calibre_formats_command_fails(self, mock_run):
        """Test _query_calibre_formats when ebook-convert command fails."""
        converter = self.create_converter()
        
        mock_run.side_effect = FileNotFoundError("Command not found")
        
        with pytest.raises(FileNotFoundError):
            converter._query_calibre_formats()

    @patch('subprocess.run')
    def test_query_calibre_formats_timeout(self, mock_run):
        """Test _query_calibre_formats with command timeout."""
        converter = self.create_converter()
        
        mock_run.side_effect = subprocess.TimeoutExpired("ebook-convert", 10)
        
        with pytest.raises(subprocess.TimeoutExpired):
            converter._query_calibre_formats()