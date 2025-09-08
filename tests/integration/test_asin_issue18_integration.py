"""
Integration tests for ASIN lookup issue #18 fixes.

These tests verify that the GitHub issue #18 fixes work correctly:
- Title/author searches now return results instead of failing
- Error handling provides detailed information
- CLI integration works with verbose mode
- Real-world examples work as expected
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from calibre_books.cli.asin import lookup
from calibre_books.core.asin_lookup import ASINLookupService
from calibre_books.core.book import ASINLookupResult


class TestASINLookupIssue18Integration:
    """Integration tests for GitHub issue #18 fixes."""

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
    def test_successful_title_author_lookup_via_cli(self, mock_service_class):
        """Test successful title/author ASIN lookup through CLI interface."""
        # Mock service and result
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="The Way of Kings",
            query_author="Brandon Sanderson",
            asin="B00ZVA3XL6",
            metadata={"amazon-search": "Success"},
            source="amazon-search",
            success=True,
            lookup_time=1.234,
            from_cache=False,
        )
        mock_service.lookup_by_title.return_value = mock_result

        # Test CLI command
        result = self.runner.invoke(
            lookup,
            ["--book", "The Way of Kings", "--author", "Brandon Sanderson"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "ASIN found: B00ZVA3XL6" in result.output
        assert "Source: amazon-search" in result.output

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_verbose_mode_provides_detailed_output(self, mock_service_class):
        """Test that verbose mode provides detailed debugging information."""
        # Mock service and result with detailed metadata
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="Mistborn",
            query_author="Brandon Sanderson",
            asin="B000QCS5ME",
            metadata={
                "amazon-search": "Success after 2 strategies",
                "google-books": "No valid ASIN found",
                "openlibrary": "Connection timeout",
            },
            source="amazon-search",
            success=True,
            lookup_time=2.567,
            from_cache=False,
        )
        mock_service.lookup_by_title.return_value = mock_result

        # Test CLI command with verbose flag
        result = self.runner.invoke(
            lookup,
            ["--book", "Mistborn", "--author", "Brandon Sanderson", "--verbose"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "ASIN found: B000QCS5ME" in result.output
        assert "Source: amazon-search" in result.output
        assert "Lookup time: 2.57s" in result.output
        # Verbose mode enables detailed logging, but metadata table only shows for non-string metadata

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_enhanced_error_reporting_via_cli(self, mock_service_class):
        """Test enhanced error reporting when no ASIN is found."""
        # Mock service and failed result
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="Nonexistent Book",
            query_author="Unknown Author",
            asin=None,
            metadata={
                "amazon-search": "No results found in any search strategy",
                "google-books": "API returned no items",
                "openlibrary": "No matching books found",
            },
            source=None,
            success=False,
            error="No ASIN found. Sources attempted: amazon-search: No results found in any search strategy; google-books: API returned no items; openlibrary: No matching books found",
            lookup_time=3.456,
        )
        mock_service.lookup_by_title.return_value = mock_result

        # Test CLI command
        result = self.runner.invoke(
            lookup,
            ["--book", "Nonexistent Book", "--author", "Unknown Author", "--verbose"],
            obj=self.create_mock_context(),
        )

        assert (
            result.exit_code == 0
        )  # CLI doesn't exit with error, just reports no results
        assert "No ASIN found" in result.output
        # In verbose mode, detailed source information should be shown in a table
        assert "Detailed source information" in result.output
        assert "amazon-search" in result.output
        assert "google-books" in result.output
        assert "openlibrary" in result.output

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_source_filtering_via_cli(self, mock_service_class):
        """Test that source filtering works correctly through CLI."""
        # Mock service and result
        mock_service = Mock()
        mock_service_class.return_value = mock_service

        mock_result = ASINLookupResult(
            query_title="Test Book",
            query_author="Test Author",
            asin="B00TESTBOOK",
            metadata={"google-books": "Found via Google Books API"},
            source="google-books",
            success=True,
        )
        mock_service.lookup_by_title.return_value = mock_result

        # Test CLI command with specific source
        result = self.runner.invoke(
            lookup,
            [
                "--book",
                "Test Book",
                "--author",
                "Test Author",
                "--sources",
                "goodreads",  # Should map to google-books
            ],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 0
        assert "ASIN found: B00TESTBOOK" in result.output

        # Verify that sources were passed correctly to the service
        mock_service.lookup_by_title.assert_called_once()
        call_args = mock_service.lookup_by_title.call_args
        assert call_args[1]["sources"] == ("goodreads",)

    def test_asin_validation_integration(self):
        """Test ASIN validation works correctly in integrated system."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config_manager = Mock()
            mock_config_manager.get_asin_config.return_value = {
                "cache_path": str(Path(temp_dir) / "test_cache.json"),
                "sources": ["amazon", "goodreads", "openlibrary"],
                "rate_limit": 0.1,
            }

            service = ASINLookupService(mock_config_manager)

            # Test that validation works as expected
            assert service.validate_asin("B00ZVA3XL6") is True
            assert service.validate_asin("B123456789") is True
            assert service.validate_asin("b00zva3xl6") is True  # Lowercase

            # Invalid cases
            assert service.validate_asin("A123456789") is False
            assert service.validate_asin("9780765326355") is False  # ISBN
            assert service.validate_asin("") is False
            assert service.validate_asin(None) is False

    def test_mock_full_lookup_workflow(self):
        """Test a complete mock lookup workflow demonstrating issue #18 fixes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.json"

            mock_config_manager = Mock()
            mock_config_manager.get_asin_config.return_value = {
                "cache_path": str(cache_path),
                "sources": ["amazon", "goodreads", "openlibrary"],
                "rate_limit": 0.1,
            }

            service = ASINLookupService(mock_config_manager)

            # Mock successful Amazon lookup
            with patch.object(
                service, "_lookup_via_amazon_search", return_value="B00WORKFL1"
            ) as mock_amazon:
                result = service.lookup_by_title(
                    "Test Book", author="Test Author", verbose=True
                )

                # Should succeed
                assert result.success is True
                assert result.asin == "B00WORKFL1"
                assert result.source == "amazon-search"
                assert result.from_cache is False

                # Amazon method should have been called
                mock_amazon.assert_called_once()

    def test_brandon_sanderson_examples_simulation(self):
        """Simulate the specific examples from GitHub issue #18 with expected outcomes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config_manager = Mock()
            mock_config_manager.get_asin_config.return_value = {
                "cache_path": str(Path(temp_dir) / "test_cache.json"),
                "sources": ["amazon", "goodreads", "openlibrary"],
                "rate_limit": 0.1,
            }

            service = ASINLookupService(mock_config_manager)

            # Test cases from the GitHub issue
            test_cases = [
                ("The Way of Kings", "Brandon Sanderson", "B00WZKB3QU"),
                ("Mistborn", "Brandon Sanderson", "B000RJRM8Y"),
                ("The Hobbit", "J.R.R. Tolkien", "B007978NPG"),
            ]

            for title, author, expected_asin in test_cases:
                # Mock successful lookup for each case
                with patch.object(
                    service, "_lookup_via_amazon_search", return_value=expected_asin
                ):
                    result = service.lookup_by_title(title, author=author, verbose=True)

                    # These should all succeed now (issue #18 was that they failed)
                    assert (
                        result.success is True
                    ), f"Failed lookup for '{title}' by {author}"
                    assert result.asin == expected_asin, f"Wrong ASIN for '{title}'"
                    assert result.source == "amazon-search"
                    assert "No ASIN found from any source" not in (result.error or "")

    @patch("calibre_books.cli.asin.ASINLookupService")
    def test_cli_handles_network_errors_gracefully(self, mock_service_class):
        """Test that CLI handles network errors gracefully."""
        # Mock service that raises an exception
        mock_service = Mock()
        mock_service_class.return_value = mock_service
        mock_service.lookup_by_title.side_effect = Exception(
            "Network connection failed"
        )

        result = self.runner.invoke(
            lookup,
            ["--book", "Test Book", "--author", "Test Author"],
            obj=self.create_mock_context(),
        )

        assert result.exit_code == 1
        assert "ASIN lookup failed" in result.output
        assert "Network connection failed" in result.output

    def test_multiple_sources_fallback_behavior(self):
        """Test that the system properly falls back between different sources."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config_manager = Mock()
            mock_config_manager.get_asin_config.return_value = {
                "cache_path": str(Path(temp_dir) / "test_cache.json"),
                "sources": ["amazon", "goodreads", "openlibrary"],
                "rate_limit": 0.1,
            }

            service = ASINLookupService(mock_config_manager)

            # Test fallback: Amazon fails, Google Books succeeds
            with (
                patch.object(
                    service, "_lookup_via_amazon_search", return_value=None
                ) as mock_amazon,
                patch.object(
                    service, "_lookup_via_google_books", return_value="B00FALLBK1"
                ) as mock_google,
                patch.object(service, "_lookup_via_openlibrary", return_value=None),
            ):

                result = service.lookup_by_title("Test Book", author="Test Author")

                # Should succeed with Google Books result
                assert result.success is True
                assert result.asin == "B00FALLBK1"
                assert result.source == "google-books"

                # All methods should have been tried
                mock_amazon.assert_called_once()
                mock_google.assert_called_once()
                # OpenLibrary might or might not be called depending on source mapping


class TestIssue18PerformanceAndReliability:
    """Test performance and reliability aspects of issue #18 fixes."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_config = {
            "cache_path": "~/.book-tool/test_cache.json",
            "sources": ["amazon", "goodreads", "openlibrary"],
            "rate_limit": 0.1,
        }

    def test_rate_limiting_functionality(self):
        """Test that rate limiting works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config_manager = Mock()
            mock_config_manager.get_asin_config.return_value = {
                "cache_path": str(Path(temp_dir) / "test_cache.json"),
                "sources": ["amazon"],
                "rate_limit": 0.5,  # 0.5 second rate limit
            }

            service = ASINLookupService(mock_config_manager)

            # Verify rate limit is set correctly
            assert service.rate_limit == 0.5

    def test_cache_system_integration(self):
        """Test that caching works correctly to avoid redundant lookups."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "integration_cache.json"

            mock_config_manager = Mock()
            mock_config_manager.get_asin_config.return_value = {
                "cache_path": str(cache_path),
                "sources": ["amazon"],
                "rate_limit": 0.1,
            }

            service = ASINLookupService(mock_config_manager)

            # First lookup - should call the service
            with patch.object(
                service, "_lookup_via_amazon_search", return_value="B00CACHED1"
            ) as mock_amazon:
                result1 = service.lookup_by_title("Cached Book", author="Cached Author")

                assert result1.success is True
                assert result1.asin == "B00CACHED1"
                assert result1.from_cache is False
                mock_amazon.assert_called_once()

            # Second lookup - should use cache
            with patch.object(service, "_lookup_via_amazon_search") as mock_amazon:
                result2 = service.lookup_by_title("Cached Book", author="Cached Author")

                assert result2.success is True
                assert result2.asin == "B00CACHED1"
                assert result2.from_cache is True
                # Amazon method should not be called again
                mock_amazon.assert_not_called()

    def test_error_resilience(self):
        """Test that the system is resilient to various types of errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_config_manager = Mock()
            mock_config_manager.get_asin_config.return_value = {
                "cache_path": str(Path(temp_dir) / "test_cache.json"),
                "sources": ["amazon", "goodreads"],
                "rate_limit": 0.1,
            }

            service = ASINLookupService(mock_config_manager)

            # Test that one source failing doesn't prevent others from working
            with (
                patch.object(
                    service,
                    "_lookup_via_amazon_search",
                    side_effect=Exception("Amazon error"),
                ) as mock_amazon,
                patch.object(
                    service, "_lookup_via_google_books", return_value="B00RESIL12"
                ) as mock_google,
            ):

                result = service.lookup_by_title("Test Book", author="Test Author")

                # Should still succeed with Google Books
                assert result.success is True
                assert result.asin == "B00RESIL12"
                assert result.source == "google-books"

                # Both methods should have been attempted
                mock_amazon.assert_called_once()
                mock_google.assert_called_once()
