"""
Unit tests for Calibre integration functionality.

Tests the CalibreIntegration and CalibreDB classes including CLI wrapper,
error handling, and data conversion utilities.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.calibre_books.core.calibre import (
    CalibreIntegration,
    CalibreDB,
    CalibreResult,
    CalibreError,
    CalibreNotFoundError,
    LibraryNotFoundError,
)
from src.calibre_books.core.book import Book, LibraryStats
from src.calibre_books.config.manager import ConfigManager


class TestCalibreDB:
    """Test the CalibreDB CLI wrapper class."""

    def test_init_with_auto_detection(self):
        """Test CalibreDB initialization with auto CLI detection."""
        library_path = Path("/test/library")

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = Mock(returncode=0, stdout="calibre 5.0")

            # Mock the validation methods
            with (
                patch.object(CalibreDB, "_validate_library"),
                patch.object(CalibreDB, "_validate_cli"),
            ):
                calibre_db = CalibreDB(library_path, "auto")

                assert calibre_db.library_path == library_path
                assert (
                    calibre_db.cli_path == "calibredb"
                )  # Default first path that works

    def test_init_library_not_found(self):
        """Test initialization with non-existent library."""
        library_path = Path("/nonexistent/library")

        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(LibraryNotFoundError):
                CalibreDB(library_path, "calibredb")

    def test_calibre_cli_not_found(self):
        """Test initialization when Calibre CLI is not found."""
        library_path = Path("/test/library")

        with (
            patch.object(Path, "exists", return_value=True),
            patch("subprocess.run", side_effect=FileNotFoundError()),
        ):
            with pytest.raises(CalibreNotFoundError):
                CalibreDB(library_path, "auto")

    def test_execute_command_success(self):
        """Test successful command execution."""
        library_path = Path("/test/library")

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(CalibreDB, "_validate_library"),
            patch.object(CalibreDB, "_validate_cli"),
            patch("subprocess.run") as mock_run,
        ):

            mock_run.return_value = Mock(
                returncode=0, stdout='{"test": "data"}', stderr=""
            )

            calibre_db = CalibreDB(library_path, "calibredb")
            result = calibre_db.execute_command(["list", "--for-machine"])

            assert result.success
            assert result.output == '{"test": "data"}'
            assert result.return_code == 0
            assert result.has_data

    def test_execute_command_failure(self):
        """Test command execution failure."""
        library_path = Path("/test/library")

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(CalibreDB, "_validate_library"),
            patch.object(CalibreDB, "_validate_cli"),
            patch("subprocess.run") as mock_run,
        ):

            mock_run.return_value = Mock(
                returncode=1, stdout="", stderr="Command failed"
            )

            calibre_db = CalibreDB(library_path, "calibredb")
            result = calibre_db.execute_command(["invalid", "command"])

            assert not result.success
            assert result.error == "Command failed"
            assert result.return_code == 1
            assert not result.has_data

    def test_list_books(self):
        """Test book listing functionality."""
        library_path = Path("/test/library")

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(CalibreDB, "_validate_library"),
            patch.object(CalibreDB, "_validate_cli"),
            patch.object(CalibreDB, "execute_command") as mock_exec,
        ):

            mock_exec.return_value = CalibreResult(
                success=True,
                output='[{"id": 1, "title": "Test Book"}]',
                error="",
                return_code=0,
                command=["calibredb", "list"],
            )

            calibre_db = CalibreDB(library_path, "calibredb")
            result = calibre_db.list_books(fields=["id", "title"])

            assert result.success
            mock_exec.assert_called_once_with(
                ["list", "--fields", "id,title", "--for-machine"]
            )


class TestCalibreIntegration:
    """Test the CalibreIntegration class functionality."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        config_manager = Mock(spec=ConfigManager)
        config_manager.get_calibre_config.return_value = {
            "library_path": "/test/library",
            "cli_path": "auto",
        }
        return config_manager

    @pytest.fixture
    def calibre_integration(self, mock_config_manager):
        """Create a CalibreIntegration instance with mocked dependencies."""
        with patch.object(Path, "expanduser", return_value=Path("/test/library")):
            integration = CalibreIntegration(mock_config_manager)
            # Mock the CalibreDB to prevent initialization issues
            integration._calibre_db = Mock()
            return integration

    def test_init(self, mock_config_manager):
        """Test CalibreIntegration initialization."""
        with patch.object(Path, "expanduser", return_value=Path("/test/library")):
            integration = CalibreIntegration(mock_config_manager)

            assert integration.config_manager == mock_config_manager
            assert integration.library_path == Path("/test/library")
            assert integration.cli_path == "auto"

    def test_get_library_stats_success(self, calibre_integration):
        """Test successful library statistics retrieval."""
        mock_books_data = [
            {
                "id": 1,
                "title": "Test Book 1",
                "authors": ["Author One"],
                "series": "Test Series",
                "formats": ["EPUB"],
                "size": 1024000,
            },
            {
                "id": 2,
                "title": "Test Book 2",
                "authors": ["Author Two"],
                "series": None,
                "formats": ["PDF"],
                "size": 2048000,
            },
        ]

        mock_db = calibre_integration._calibre_db
        mock_result = Mock()
        mock_result.success = True
        mock_result.has_data = True
        mock_result.output = json.dumps(mock_books_data)
        mock_db.list_books.return_value = mock_result

        # Mock additional calls for detailed stats
        mock_db.find_duplicates.return_value = Mock(success=True, output="")

        stats = calibre_integration.get_library_stats(detailed=True)

        assert isinstance(stats, LibraryStats)
        assert stats.total_books == 2
        assert stats.total_authors == 2
        assert stats.total_series == 1
        assert stats.library_size == 3072000
        assert stats.format_distribution == {"epub": 1, "pdf": 1}

    def test_get_library_stats_calibre_error(self, calibre_integration):
        """Test library stats when Calibre command fails."""
        mock_db = calibre_integration._calibre_db
        mock_result = Mock()
        mock_result.success = False
        mock_result.error = "Library not accessible"
        mock_db.list_books.return_value = mock_result

        with pytest.raises(CalibreError):
            calibre_integration.get_library_stats()

    def test_get_books_for_asin_update(self, calibre_integration):
        """Test retrieving books for ASIN updates."""
        mock_books_data = [
            {
                "id": 1,
                "title": "Book Without ASIN",
                "authors": ["Test Author"],
                "identifiers": {},  # No ASIN
                "series": None,
                "series_index": None,
                "pubdate": "2023-01-01",
                "formats": ["EPUB"],
                "path": "Test Author/Book Without ASIN (1)",
            }
        ]

        mock_db = calibre_integration._calibre_db
        mock_result = Mock()
        mock_result.success = True
        mock_result.has_data = True
        mock_result.output = json.dumps(mock_books_data)
        mock_db.list_books.return_value = mock_result

        books = calibre_integration.get_books_for_asin_update(missing_only=True)

        assert len(books) == 1
        assert isinstance(books[0], Book)
        assert books[0].title == "Book Without ASIN"
        assert books[0].asin is None
        assert books[0].calibre_id == 1

    def test_convert_calibre_data_to_book(self, calibre_integration):
        """Test conversion from Calibre data to Book object."""
        calibre_data = {
            "id": 42,
            "title": "Test Book",
            "authors": ["John Doe", "Jane Smith"],
            "identifiers": {"amazon": "B01234567X", "isbn": "978-3-16-148410-0"},
            "series": "Test Series",
            "series_index": 1.0,
            "pubdate": "2023-01-01T00:00:00Z",
            "formats": ["EPUB", "PDF"],
            "path": "John Doe/Test Book (42)",
        }

        book = calibre_integration._convert_calibre_data_to_book(calibre_data)

        assert isinstance(book, Book)
        assert book.title == "Test Book"
        assert book.author == "John Doe"
        assert book.metadata.authors == ["John Doe", "Jane Smith"]
        assert book.asin == "B01234567X"
        assert book.isbn == "9783161484100"
        assert book.series == "Test Series"
        assert book.metadata.series_index == 1.0
        assert book.calibre_id == 42

    def test_update_asins_success(self, calibre_integration):
        """Test successful ASIN updates."""
        mock_results = [
            {"book_id": 1, "asin": "B01234567X"},
            {"book_id": 2, "asin": "B09876543Z"},
        ]

        mock_db = calibre_integration._calibre_db
        mock_db.set_metadata.return_value = Mock(success=True)

        updated_count = calibre_integration.update_asins(mock_results, dry_run=False)

        assert updated_count == 2
        assert mock_db.set_metadata.call_count == 2

    def test_update_asins_dry_run(self, calibre_integration):
        """Test ASIN updates in dry run mode."""
        mock_results = [{"book_id": 1, "asin": "B01234567X"}]

        mock_db = calibre_integration._calibre_db
        updated_count = calibre_integration.update_asins(mock_results, dry_run=True)

        assert updated_count == 1
        mock_db.set_metadata.assert_not_called()

    def test_search_library(self, calibre_integration):
        """Test library search functionality."""
        mock_books_data = [
            {
                "id": 1,
                "title": "Search Result",
                "authors": ["Test Author"],
                "identifiers": {},
                "series": None,
                "series_index": None,
                "formats": ["EPUB"],
                "path": "Test Author/Search Result (1)",
            }
        ]

        mock_db = calibre_integration._calibre_db
        mock_result = Mock()
        mock_result.success = True
        mock_result.has_data = True
        mock_result.output = json.dumps(mock_books_data)
        mock_db.list_books.return_value = mock_result

        books = calibre_integration.search_library("test query", limit=10)

        assert len(books) == 1
        assert isinstance(books[0], Book)
        assert books[0].title == "Search Result"


class TestCalibreResult:
    """Test the CalibreResult data class."""

    def test_calibre_result_success(self):
        """Test CalibreResult with successful command."""
        result = CalibreResult(
            success=True,
            output='{"data": "test"}',
            error="",
            return_code=0,
            command=["calibredb", "list"],
        )

        assert result.success
        assert result.has_data
        assert result.output == '{"data": "test"}'

    def test_calibre_result_failure(self):
        """Test CalibreResult with failed command."""
        result = CalibreResult(
            success=False,
            output="",
            error="Command failed",
            return_code=1,
            command=["calibredb", "invalid"],
        )

        assert not result.success
        assert not result.has_data
        assert result.error == "Command failed"

    def test_has_data_empty_output(self):
        """Test has_data property with empty output."""
        result = CalibreResult(
            success=True,
            output="   ",  # Just whitespace
            error="",
            return_code=0,
            command=["calibredb", "list"],
        )

        assert not result.has_data


if __name__ == "__main__":
    pytest.main([__file__])
