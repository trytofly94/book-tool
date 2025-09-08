"""
Integration tests for ASIN CLI commands.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from calibre_books.cli.asin import lookup, batch_update, cache, verify
from calibre_books.core.book import Book, BookMetadata, ASINLookupResult
from calibre_books.config.manager import ConfigManager
from calibre_books.config.schema import ConfigurationSchema


class TestASINCliCommands:
    """Test ASIN CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.test_config = {
            "asin_lookup": {
                "cache_path": "~/.book-tool/test_cache.json",
                "sources": ["amazon", "goodreads", "openlibrary"],
                "rate_limit": 0.1,
            }
        }

    def create_mock_context(self):
        """Create a mock Click context with test configuration."""
        mock_config_manager = Mock()
        mock_config_manager.get_asin_config.return_value = self.test_config[
            "asin_lookup"
        ]

        return {"config": mock_config_manager, "dry_run": False}

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_lookup_by_book_title_success(self, mock_service_class):
        """Test ASIN lookup by book title - success case."""
        # Mock service and result
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="The Way of Kings",
            query_author="Brandon Sanderson",
            asin="B00ZVA3XL6",
            metadata=None,
            source="amazon-search",
            success=True,
        )
        mock_service.lookup_by_title.return_value = mock_result

        # Test command
        result = self.runner.invoke(
            lookup,
            ["--book", "The Way of Kings", "--author", "Brandon Sanderson"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "ASIN found: B00ZVA3XL6" in result.output

        # Verify service was called correctly (ignore progress_callback as it's an internal object)
        mock_service.lookup_by_title.assert_called_once()
        call_args = mock_service.lookup_by_title.call_args
        assert call_args[0] == ("The Way of Kings",)  # Positional args
        assert call_args[1]["author"] == "Brandon Sanderson"
        assert call_args[1]["sources"] is None
        assert call_args[1]["use_cache"] is True
        assert (
            call_args[1]["progress_callback"] is not None
        )  # Should be a real callback

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_lookup_by_isbn_success(self, mock_service_class):
        """Test ASIN lookup by ISBN - success case."""
        # Mock service and result
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="ISBN:9780765326355",
            query_author=None,
            asin="B00ZVA3XL6",
            metadata=None,
            source="isbn-direct",
            success=True,
        )
        mock_service.lookup_by_isbn.return_value = mock_result

        # Test command
        result = self.runner.invoke(
            lookup, ["--isbn", "9780765326355"], obj=self.create_mock_context()
        )

        assert result.exit_code == 0
        assert "ASIN found: B00ZVA3XL6" in result.output

        # Verify service was called correctly (ignore progress_callback as it's an internal object)
        mock_service.lookup_by_isbn.assert_called_once()
        call_args = mock_service.lookup_by_isbn.call_args
        assert call_args[0] == ("9780765326355",)  # Positional args
        assert call_args[1]["sources"] is None
        assert call_args[1]["use_cache"] is True
        assert (
            call_args[1]["progress_callback"] is not None
        )  # Should be a real callback

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_lookup_no_asin_found(self, mock_service_class):
        """Test ASIN lookup with no results."""
        # Mock service and result
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="Nonexistent Book",
            query_author="Unknown Author",
            asin=None,
            metadata=None,
            source=None,
            success=False,
            error="No ASIN found from any source",
        )
        mock_service.lookup_by_title.return_value = mock_result

        # Test command
        result = self.runner.invoke(
            lookup,
            ["--book", "Nonexistent Book", "--author", "Unknown Author"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "No ASIN found" in result.output
        assert "No ASIN found from any source" in result.output

    def test_lookup_missing_parameters(self):
        """Test ASIN lookup with missing required parameters."""
        result = self.runner.invoke(lookup, [], obj=self.create_mock_context())

        assert result.exit_code == 1
        assert "Must specify either --book or --isbn" in result.output

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_lookup_with_sources_filter(self, mock_service_class):
        """Test ASIN lookup with specific sources."""
        # Mock service and result
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="Test Book",
            query_author=None,
            asin="B00TESTBOOK",
            metadata=None,
            source="amazon-search",
            success=True,
        )
        mock_service.lookup_by_title.return_value = mock_result

        # Test command with specific sources
        result = self.runner.invoke(
            lookup,
            ["--book", "Test Book", "--sources", "amazon", "--sources", "goodreads"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "ASIN found: B00TESTBOOK" in result.output

        # Verify sources were passed correctly
        mock_service.lookup_by_title.assert_called_once()
        call_args = mock_service.lookup_by_title.call_args
        assert call_args[1]["sources"] == ("amazon", "goodreads")

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_lookup_no_cache(self, mock_service_class):
        """Test ASIN lookup without cache."""
        # Mock service and result
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="Test Book",
            query_author=None,
            asin="B00TESTBOOK",
            metadata=None,
            source="amazon-search",
            success=True,
        )
        mock_service.lookup_by_title.return_value = mock_result

        # Test command without cache
        result = self.runner.invoke(
            lookup,
            ["--book", "Test Book", "--no-cache"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0

        # Verify use_cache was False
        mock_service.lookup_by_title.assert_called_once()
        call_args = mock_service.lookup_by_title.call_args
        assert call_args[1]["use_cache"] is False

    def test_lookup_dry_run(self):
        """Test ASIN lookup in dry run mode."""
        # Create dry run context
        context = self.create_mock_context()
        context["dry_run"] = True

        result = self.runner.invoke(
            lookup, ["--book", "Test Book", "--author", "Test Author"], obj=context
        )

        assert result.exit_code == 0
        assert "DRY RUN: Would lookup ASIN for:" in result.output
        assert "Book: Test Book" in result.output
        assert "Author: Test Author" in result.output

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_lookup_with_exception(self, mock_service_class):
        """Test ASIN lookup with service exception."""
        # Mock service to raise exception
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.lookup_by_title.side_effect = Exception("Service error")

        result = self.runner.invoke(
            lookup, ["--book", "Test Book"], obj=self.create_mock_context()
        )

        assert result.exit_code == 1
        assert "ASIN lookup failed: Service error" in result.output

    @patch("calibre_books.cli.asin.CalibreIntegration")
    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_batch_update_success(self, mock_service_class, mock_calibre_class):
        """Test batch ASIN update - success case."""
        # Mock Calibre integration
        mock_calibre = Mock()
        mock_calibre_class.return_value = mock_calibre

        test_books = [
            Book(
                metadata=BookMetadata(
                    title="Book 1", author="Author 1", isbn="1111111111"
                )
            ),
            Book(metadata=BookMetadata(title="Book 2", author="Author 2")),
        ]
        mock_calibre.get_books_for_asin_update.return_value = test_books
        mock_calibre.update_asins.return_value = 2

        # Mock ASIN service
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_results = [
            ASINLookupResult(
                query_title="ISBN:1111111111",
                query_author=None,
                asin="B00BOOK1",
                metadata=None,
                source="isbn-direct",
                success=True,
            ),
            ASINLookupResult(
                query_title="Book 2",
                query_author="Author 2",
                asin="B00BOOK2",
                metadata=None,
                source="amazon-search",
                success=True,
            ),
        ]
        mock_service.batch_update.return_value = mock_results

        # Test command
        result = self.runner.invoke(
            batch_update,
            ["--missing-only", "--parallel", "2"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "Batch ASIN update completed" in result.output
        assert "Books processed: 2" in result.output
        assert "ASINs found: 2" in result.output
        assert "Library updated: 2" in result.output

        # Verify service calls (ignore progress_callback as it's an internal object)
        mock_service.batch_update.assert_called_once()
        call_args = mock_service.batch_update.call_args
        assert len(call_args[0][0]) == 2  # Two books passed
        assert call_args[1]["sources"] is None
        assert call_args[1]["parallel"] == 2
        assert (
            call_args[1]["progress_callback"] is not None
        )  # Should be a real callback

    @patch("calibre_books.cli.asin.CalibreIntegration")
    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_batch_update_no_books(self, mock_service_class, mock_calibre_class):
        """Test batch ASIN update with no books found."""
        # Mock Calibre integration to return no books
        mock_calibre = Mock()
        mock_calibre_class.return_value = mock_calibre
        mock_calibre.get_books_for_asin_update.return_value = []

        result = self.runner.invoke(batch_update, [], obj=self.create_mock_context())

        assert result.exit_code == 0
        assert "No books found matching criteria" in result.output

    def test_batch_update_dry_run(self):
        """Test batch ASIN update in dry run mode."""
        # Mock Calibre integration
        with patch("calibre_books.cli.asin.CalibreIntegration") as mock_calibre_class:
            mock_calibre = Mock()
            mock_calibre_class.return_value = mock_calibre

            test_books = [
                Book(metadata=BookMetadata(title="Book 1", author="Author 1")),
                Book(metadata=BookMetadata(title="Book 2", author="Author 2")),
                Book(metadata=BookMetadata(title="Book 3", author="Author 3")),
                Book(metadata=BookMetadata(title="Book 4", author="Author 4")),
                Book(metadata=BookMetadata(title="Book 5", author="Author 5")),
                Book(
                    metadata=BookMetadata(title="Book 6", author="Author 6")
                ),  # More than 5 to test truncation
            ]
            mock_calibre.get_books_for_asin_update.return_value = test_books

            # Create dry run context
            context = self.create_mock_context()
            context["dry_run"] = True

            result = self.runner.invoke(batch_update, [], obj=context)

            assert result.exit_code == 0
            assert "DRY RUN: Would update ASINs for 6 books:" in result.output
            assert "Book 1 by Author 1" in result.output
            assert "... and 1 more" in result.output  # Truncation message

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_cache_show_stats(self, mock_service_class):
        """Test cache show stats command."""
        # Mock service and cache manager
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_cache_manager = Mock()
        mock_service.cache_manager = mock_cache_manager

        # Mock stats dataclass
        from dataclasses import dataclass
        from datetime import datetime

        @dataclass
        class MockStats:
            total_entries: int = 150
            hit_rate: float = 0.75
            size_human: str = "2.5 KB"
            last_updated: datetime = datetime(2025, 9, 6, 12, 0, 0)

        mock_cache_manager.get_stats.return_value = MockStats()

        result = self.runner.invoke(
            cache, ["--show-stats"], obj=self.create_mock_context()
        )

        assert result.exit_code == 0
        assert "ASIN Cache Statistics" in result.output
        assert "150" in result.output  # total_entries
        assert "75.0%" in result.output  # hit_rate
        assert "2.5 KB" in result.output  # size_human

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_cache_clear(self, mock_service_class):
        """Test cache clear command."""
        # Mock service and cache manager
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_cache_manager = Mock()
        mock_service.cache_manager = mock_cache_manager

        result = self.runner.invoke(cache, ["--clear"], obj=self.create_mock_context())

        assert result.exit_code == 0
        assert "ASIN cache cleared" in result.output

        # Verify cache was cleared
        mock_cache_manager.clear.assert_called_once()

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_cache_cleanup(self, mock_service_class):
        """Test cache cleanup command."""
        # Mock service and cache manager
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_cache_manager = Mock()
        mock_service.cache_manager = mock_cache_manager
        mock_cache_manager.cleanup_expired.return_value = 5  # 5 expired entries removed

        result = self.runner.invoke(
            cache, ["--cleanup"], obj=self.create_mock_context()
        )

        assert result.exit_code == 0
        assert "Removed 5 expired cache entries" in result.output

        # Verify cleanup was called
        mock_cache_manager.cleanup_expired.assert_called_once()

    def test_cache_dry_run(self):
        """Test cache operations in dry run mode."""
        # Create dry run context
        context = self.create_mock_context()
        context["dry_run"] = True

        result = self.runner.invoke(cache, ["--clear"], obj=context)

        assert result.exit_code == 0
        assert "DRY RUN: Would clear ASIN cache" in result.output

    def test_cache_no_options(self):
        """Test cache command with no options."""
        result = self.runner.invoke(cache, [], obj=self.create_mock_context())

        assert result.exit_code == 0
        assert "Use --show-stats, --clear, or --cleanup" in result.output

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_verify_valid_asin(self, mock_service_class):
        """Test ASIN verification with valid ASIN."""
        # Mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.validate_asin.return_value = True

        result = self.runner.invoke(
            verify, ["--asin", "B00ZVA3XL6"], obj=self.create_mock_context()
        )

        assert result.exit_code == 0
        assert "ASIN format is valid: B00ZVA3XL6" in result.output

        # Verify validation was called
        mock_service.validate_asin.assert_called_once_with("B00ZVA3XL6")

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_verify_invalid_asin(self, mock_service_class):
        """Test ASIN verification with invalid ASIN."""
        # Mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.validate_asin.return_value = False

        result = self.runner.invoke(
            verify, ["--asin", "INVALID"], obj=self.create_mock_context()
        )

        assert result.exit_code == 1
        assert "Invalid ASIN format: INVALID" in result.output

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_verify_with_availability_check_available(self, mock_service_class):
        """Test ASIN verification with availability check - available."""
        # Mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.validate_asin.return_value = True

        # Mock availability check
        from dataclasses import dataclass

        @dataclass
        class MockAvailability:
            available: bool = True
            metadata: dict = None

            def __post_init__(self):
                if self.metadata is None:
                    self.metadata = {"title": "Test Book Title", "price": "$9.99"}

        mock_service.check_availability.return_value = MockAvailability()

        result = self.runner.invoke(
            verify,
            ["--asin", "B00ZVA3XL6", "--check-availability"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "ASIN format is valid: B00ZVA3XL6" in result.output
        assert "ASIN is available on Amazon" in result.output
        assert "Title: Test Book Title" in result.output
        assert "Price: $9.99" in result.output

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_verify_with_availability_check_unavailable(self, mock_service_class):
        """Test ASIN verification with availability check - unavailable."""
        # Mock service
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.validate_asin.return_value = True

        # Mock availability check
        from dataclasses import dataclass

        @dataclass
        class MockAvailability:
            available: bool = False
            metadata: dict = None

        mock_service.check_availability.return_value = MockAvailability()

        result = self.runner.invoke(
            verify,
            ["--asin", "B00ZVA3XL6", "--check-availability"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "ASIN format is valid: B00ZVA3XL6" in result.output
        assert "ASIN is not available or restricted" in result.output

    def test_verify_dry_run(self):
        """Test ASIN verification in dry run mode."""
        # Create dry run context
        context = self.create_mock_context()
        context["dry_run"] = True

        result = self.runner.invoke(
            verify, ["--asin", "B00ZVA3XL6", "--check-availability"], obj=context
        )

        assert result.exit_code == 0
        assert "DRY RUN: Would verify ASIN: B00ZVA3XL6" in result.output
        assert "Would check availability on Amazon" in result.output

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_verify_with_exception(self, mock_service_class):
        """Test ASIN verification with service exception."""
        # Mock service to raise exception
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.validate_asin.side_effect = Exception("Validation error")

        result = self.runner.invoke(
            verify, ["--asin", "B00ZVA3XL6"], obj=self.create_mock_context()
        )

        assert result.exit_code == 1
        assert "ASIN verification failed: Validation error" in result.output


class TestASINCliIntegrationWithRealConfig:
    """Integration tests using real configuration schemas."""

    def test_lookup_with_real_config_schema(self):
        """Test ASIN lookup command with real configuration schema."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yml"

            # Create real configuration
            config_manager = ConfigManager(config_path)
            ConfigurationSchema()

            # Save default configuration
            config_dict = {
                "asin_lookup": {
                    "cache_path": str(Path(temp_dir) / "asin_cache.json"),
                    "sources": ["amazon", "goodreads"],
                    "rate_limit": 0.1,
                }
            }
            config_manager.save_config(config_dict)

            # Create context with real config manager
            context = {
                "config": config_manager,
                "dry_run": True,  # Use dry run to avoid actual network calls
            }

            runner = CliRunner()
            result = runner.invoke(
                lookup, ["--book", "Test Book", "--author", "Test Author"], obj=context
            )

            assert result.exit_code == 0
            assert "DRY RUN: Would lookup ASIN for:" in result.output
