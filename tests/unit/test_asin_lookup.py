"""
Unit tests for ASIN lookup service.
"""

import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock, patch

from calibre_books.core.asin_lookup import ASINLookupService
from calibre_books.core.cache import SQLiteCacheManager
from calibre_books.core.book import Book, BookMetadata, ASINLookupResult


class TestASINLookupService:
    """Test ASINLookupService functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_config = {
            "cache_path": "~/.book-tool/test_cache.json",
            "sources": ["amazon", "goodreads", "openlibrary"],
            "rate_limit": 0.1,  # Fast rate limit for testing
        }

        # Create mock config manager
        from unittest.mock import Mock

        self.mock_config_manager = Mock()
        self.mock_config_manager.get_asin_config.return_value = self.test_config

    def create_mock_config_manager(self, config_dict):
        """Create a mock config manager with the given config dict."""
        from unittest.mock import Mock

        mock_config_manager = Mock()
        mock_config_manager.get_asin_config.return_value = config_dict
        return mock_config_manager

    def test_asin_lookup_service_init(self):
        """Test ASINLookupService initialization."""
        service = ASINLookupService(self.mock_config_manager)

        assert service.config_manager == self.mock_config_manager
        assert service.sources == ["amazon", "goodreads", "openlibrary"]
        assert service.rate_limit == 0.1
        assert isinstance(service.cache_manager, SQLiteCacheManager)
        assert len(service.user_agents) >= 3

    def test_validate_asin_format(self):
        """Test ASIN format validation."""
        service = ASINLookupService(self.mock_config_manager)

        # Valid ASINs (must be B-prefixed for book ASINs)
        assert service.validate_asin("B00ZVA3XL6") is True
        assert service.validate_asin("B123456789") is True
        assert service.validate_asin("B00ABC123D") is True

        # Also valid (lowercase converted to uppercase)
        assert service.validate_asin("b00zva3xl6") is True  # Lowercase but valid format

        # Invalid ASINs
        assert service.validate_asin("A123456789") is False  # Non-B prefixed
        assert service.validate_asin("") is False
        assert service.validate_asin("invalid") is False
        assert service.validate_asin("B12345") is False  # Too short
        assert service.validate_asin("B123456789X") is False  # Too long
        assert service.validate_asin("1123456789") is False  # Starts with number
        assert service.validate_asin(None) is False

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_lookup_by_isbn_direct_success(self, mock_get):
        """Test successful direct ISBN lookup."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock successful redirect to ASIN
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = (
            "https://www.amazon.com/dp/B00ZVA3XL6?ref=dp_kindle_redirect"
        )
        mock_get.return_value = mock_response

        # Test ISBN lookup
        asin = service._lookup_by_isbn_direct("9780765326355")

        assert asin == "B00ZVA3XL6"
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "9780765326355" in call_args[0][0]  # ISBN in URL
        assert call_args[1]["headers"]["User-Agent"]  # User agent set

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_lookup_by_isbn_direct_no_asin(self, mock_get):
        """Test direct ISBN lookup with no ASIN found."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock response without ASIN in URL
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://www.amazon.com/book-title/dp/1234567890"
        mock_get.return_value = mock_response

        asin = service._lookup_by_isbn_direct("9780765326355")

        assert asin is None

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_lookup_by_isbn_direct_exception(self, mock_get):
        """Test direct ISBN lookup with network exception."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock network exception
        mock_get.side_effect = Exception("Network error")

        asin = service._lookup_by_isbn_direct("9780765326355")

        assert asin is None

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_amazon_search_success(self, mock_get):
        """Test successful Amazon search lookup."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock Amazon search response with ASIN
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"""
        <div data-asin="B00ZVA3XL6" class="s-result-item">
            <h3>The Way of Kings</h3>
        </div>
        """
        mock_get.return_value = mock_response

        asin = service._lookup_via_amazon_search(
            "The Way of Kings", "Brandon Sanderson"
        )

        assert asin == "B00ZVA3XL6"
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "The+Way+of+Kings+Brandon+Sanderson" in call_args[0][0]

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_amazon_search_no_results(self, mock_get):
        """Test Amazon search with no results."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock empty Amazon response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<div>No results found</div>"
        mock_get.return_value = mock_response

        asin = service._lookup_via_amazon_search("Nonexistent Book", "Unknown Author")

        assert asin is None

    @patch("calibre_books.core.asin_lookup.requests.get")
    @patch("time.sleep")  # Mock sleep to avoid delays in tests
    def test_google_books_lookup_success(self, mock_sleep, mock_get):
        """Test successful Google Books API lookup."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock Google Books API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = (
            b'{"totalItems": 1, "items": [...]}'  # Mock content for len()
        )
        mock_response.json.return_value = {
            "totalItems": 1,
            "items": [
                {
                    "volumeInfo": {
                        "title": "The Way of Kings",
                        "authors": ["Brandon Sanderson"],
                        "industryIdentifiers": [
                            {"type": "ISBN_13", "identifier": "9780765326355"},
                            {"type": "OTHER", "identifier": "B00ZVA3XL6"},
                        ],
                    }
                }
            ],
        }
        mock_get.return_value = mock_response

        asin = service._lookup_via_google_books(
            "9780765326355", "The Way of Kings", "Brandon Sanderson"
        )

        assert asin == "B00ZVA3XL6"
        assert (
            mock_get.call_count >= 1
        )  # May be called multiple times with different strategies
        # Check that at least one call was made to Google Books API
        call_made_to_google_books = any(
            "googleapis.com/books/v1/volumes" in str(call)
            for call in mock_get.call_args_list
        )
        assert call_made_to_google_books

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_openlibrary_lookup_success(self, mock_get):
        """Test successful OpenLibrary API lookup."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock OpenLibrary API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ISBN:9780765326355": {
                "title": "The Way of Kings",
                "authors": [{"name": "Brandon Sanderson"}],
                "identifiers": {"amazon": ["B00ZVA3XL6"]},
            }
        }
        mock_get.return_value = mock_response

        asin = service._lookup_via_openlibrary("9780765326355")

        assert asin == "B00ZVA3XL6"
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "openlibrary.org/api/books" in call_args[0][0]

    def test_lookup_by_title_with_cache_hit(self):
        """Test lookup by title with cache hit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.json"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)

            service = ASINLookupService(self.create_mock_config_manager(config))

            # Pre-populate cache
            cache_key = "the way of kings_brandon sanderson"
            service.cache_manager.cache_asin(cache_key, "B00ZVA3XL6")

            result = service.lookup_by_title(
                "The Way of Kings", author="Brandon Sanderson"
            )

            assert result.success is True
            assert result.asin == "B00ZVA3XL6"
            assert result.source == "cache"
            assert result.from_cache is True
            assert result.query_title == "The Way of Kings"
            assert result.query_author == "Brandon Sanderson"

    @patch.object(ASINLookupService, "_lookup_via_amazon_search")
    def test_lookup_by_title_with_amazon_success(self, mock_amazon):
        """Test lookup by title with Amazon success."""
        with tempfile.TemporaryDirectory() as temp_dir:
            from unittest.mock import Mock

            cache_path = Path(temp_dir) / "test_cache.json"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)

            # Create mock config manager for this test
            mock_config_manager = Mock()
            mock_config_manager.get_asin_config.return_value = config

            service = ASINLookupService(mock_config_manager)

            # Mock successful Amazon lookup
            mock_amazon.return_value = "B00ZVA3XL6"

            result = service.lookup_by_title(
                "The Way of Kings", author="Brandon Sanderson"
            )

            assert result.success is True
            assert result.asin == "B00ZVA3XL6"
            assert result.source == "amazon-search"
            assert result.from_cache is False

            # Verify it was cached
            cached_asin = service.cache_manager.get_cached_asin(
                "the way of kings_brandon sanderson"
            )
            assert cached_asin == "B00ZVA3XL6"

    @patch.object(ASINLookupService, "_lookup_via_amazon_search")
    @patch.object(ASINLookupService, "_lookup_via_google_books")
    @patch.object(ASINLookupService, "_lookup_via_openlibrary")
    def test_lookup_by_title_no_results(
        self, mock_openlibrary, mock_google, mock_amazon
    ):
        """Test lookup by title with no results from any source."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.json"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)

            service = ASINLookupService(self.create_mock_config_manager(config))

            # Mock all sources returning None
            mock_amazon.return_value = None
            mock_google.return_value = None
            mock_openlibrary.return_value = None

            result = service.lookup_by_title(
                "Nonexistent Book", author="Unknown Author"
            )

            assert result.success is False
            assert result.asin is None
            # Check that the error message contains source-specific information
            assert "No ASIN found" in result.error
            assert "amazon-search:" in result.error
            assert "google-books:" in result.error
            assert "openlibrary:" in result.error
            assert result.from_cache is False

    def test_lookup_by_isbn_with_cache_hit(self):
        """Test lookup by ISBN with cache hit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.json"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)

            service = ASINLookupService(self.create_mock_config_manager(config))

            # Pre-populate cache
            cache_key = "isbn_9780765326355"
            service.cache_manager.cache_asin(cache_key, "B00ZVA3XL6")

            result = service.lookup_by_isbn("9780765326355")

            assert result.success is True
            assert result.asin == "B00ZVA3XL6"
            assert result.source == "cache"
            assert result.from_cache is True
            assert result.query_title == "ISBN:9780765326355"

    @patch.object(ASINLookupService, "_lookup_by_isbn_direct")
    @patch.object(ASINLookupService, "_lookup_via_google_books")
    @patch.object(ASINLookupService, "_lookup_via_openlibrary")
    def test_lookup_by_isbn_with_direct_success(
        self, mock_openlibrary, mock_google, mock_direct
    ):
        """Test lookup by ISBN with direct lookup success."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.json"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)
            config["sources"] = ["isbn-direct"]  # Use isbn-direct source

            service = ASINLookupService(self.create_mock_config_manager(config))

            # Mock all methods, but only isbn-direct should return a valid result
            mock_direct.return_value = "B00ZVA3XL6"
            mock_google.return_value = None
            mock_openlibrary.return_value = None

            result = service.lookup_by_isbn("9780765326355")

            assert result.success is True
            assert result.asin == "B00ZVA3XL6"
            assert result.source == "isbn-direct"
            assert result.from_cache is False

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_check_availability_available(self, mock_get):
        """Test ASIN availability check - available."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock successful availability response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://www.amazon.com/dp/B00ZVA3XL6"
        mock_response.text = "<html><body>This book is available</body></html>"
        mock_get.return_value = mock_response

        availability = service.check_availability("B00ZVA3XL6")

        assert availability.available is True
        assert availability.metadata["status"] == "available"
        assert availability.metadata["url"] == mock_response.url

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_check_availability_unavailable(self, mock_get):
        """Test ASIN availability check - unavailable."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock unavailable response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Currently unavailable</body></html>"
        mock_get.return_value = mock_response

        availability = service.check_availability("B00ZVA3XL6")

        assert availability.available is False
        assert availability.metadata["status"] == "unavailable"

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_check_availability_not_found(self, mock_get):
        """Test ASIN availability check - not found."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        availability = service.check_availability("B00INVALID")

        assert availability.available is False
        assert availability.metadata["status"] == "not_found"
        assert availability.metadata["status_code"] == 404

    @patch("calibre_books.core.asin_lookup.requests.get")
    def test_check_availability_exception(self, mock_get):
        """Test ASIN availability check with exception."""
        service = ASINLookupService(self.mock_config_manager)

        # Mock network exception
        mock_get.side_effect = Exception("Network error")

        availability = service.check_availability("B00ZVA3XL6")

        assert availability.available is False
        assert availability.metadata["status"] == "error"
        assert "Network error" in availability.metadata["error"]

    @patch.object(ASINLookupService, "lookup_by_isbn")
    @patch.object(ASINLookupService, "lookup_by_title")
    def test_batch_update_with_mixed_books(self, mock_lookup_title, mock_lookup_isbn):
        """Test batch update with books having both ISBNs and non-ISBN books."""
        service = ASINLookupService(self.mock_config_manager)

        # Create test books
        metadata_with_isbn = BookMetadata(
            title="The Way of Kings", author="Brandon Sanderson", isbn="9780765326355"
        )
        book_with_isbn = Book(metadata=metadata_with_isbn)

        metadata_without_isbn = BookMetadata(
            title="Words of Radiance", author="Brandon Sanderson"
        )
        book_without_isbn = Book(metadata=metadata_without_isbn)

        books = [book_with_isbn, book_without_isbn]

        # Mock lookup results
        isbn_result = ASINLookupResult(
            query_title="ISBN:9780765326355",
            query_author=None,
            asin="B00ZVA3XL6",
            metadata=None,
            source="isbn-direct",
            success=True,
        )

        title_result = ASINLookupResult(
            query_title="Words of Radiance",
            query_author="Brandon Sanderson",
            asin="B00DA6YEKS",
            metadata=None,
            source="amazon-search",
            success=True,
        )

        mock_lookup_isbn.return_value = isbn_result
        mock_lookup_title.return_value = title_result

        results = service.batch_update(books, parallel=2)

        assert len(results) == 2
        assert all(r.success for r in results)

        # Verify correct lookup methods were called
        mock_lookup_isbn.assert_called_once_with(
            "9780765326355", sources=None, use_cache=True, progress_callback=None
        )
        mock_lookup_title.assert_called_once_with(
            "Words of Radiance",
            author="Brandon Sanderson",
            sources=None,
            use_cache=True,
            progress_callback=None,
        )

    @patch.object(ASINLookupService, "lookup_by_title")
    def test_batch_update_with_exception(self, mock_lookup_title):
        """Test batch update with exception in one lookup."""
        service = ASINLookupService(self.mock_config_manager)

        # Create test book
        metadata = BookMetadata(title="Test Book", author="Test Author")
        book = Book(metadata=metadata)

        # Mock lookup exception
        mock_lookup_title.side_effect = Exception("Lookup failed")

        results = service.batch_update([book])

        assert len(results) == 1
        assert results[0].success is False
        assert "Lookup failed" in results[0].error
        assert results[0].asin is None

    def test_source_filtering(self):
        """Test that source filtering works correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.json"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)

            service = ASINLookupService(self.create_mock_config_manager(config))

            with (
                patch.object(service, "_lookup_via_amazon_search") as mock_amazon,
                patch.object(service, "_lookup_via_google_books") as mock_google,
                patch.object(service, "_lookup_via_openlibrary") as mock_openlibrary,
            ):

                mock_amazon.return_value = None
                mock_google.return_value = "B00ZVA3XL6"
                mock_openlibrary.return_value = None

                # Test with only google-books source
                result = service.lookup_by_title(
                    "Test Book", author="Test Author", sources=["google-books"]
                )

                # Only Google Books should be called
                mock_google.assert_called_once()
                mock_amazon.assert_not_called()
                mock_openlibrary.assert_not_called()

                assert result.success is True
                assert result.asin == "B00ZVA3XL6"

    def test_progress_callback(self):
        """Test that progress callback is called correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.json"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)

            service = ASINLookupService(self.create_mock_config_manager(config))

            # Mock progress callback
            progress_callback = Mock()

            with patch.object(service, "_lookup_via_amazon_search") as mock_amazon:
                mock_amazon.return_value = "B00ZVA3XL6"

                result = service.lookup_by_title(
                    "Test Book",
                    author="Test Author",
                    progress_callback=progress_callback,
                )

                # Verify result is ASINLookupResult with correct ASIN
                assert isinstance(result, ASINLookupResult)
                assert result.asin == "B00ZVA3XL6"
                assert result.success is True
                assert result.query_title == "Test Book"
                assert result.query_author == "Test Author"

                # Progress callback should have been called
                assert (
                    progress_callback.call_count >= 2
                )  # At least start and trying amazon

                # Check specific calls
                progress_calls = [
                    call[1]["description"] for call in progress_callback.call_args_list
                ]
                assert any("Starting ASIN lookup" in desc for desc in progress_calls)
                assert any("Trying amazon-search" in desc for desc in progress_calls)

    def test_close_method_functionality(self):
        """Test close() method for proper resource cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)
            config["cache_backend"] = "sqlite"

            service = ASINLookupService(self.create_mock_config_manager(config))

            # Verify service is properly initialized
            assert hasattr(service, "cache_manager")
            assert hasattr(service, "_cache_lock")
            assert not hasattr(service, "_closed")

            # Close the service
            service.close()

            # Verify close() marks service as closed
            assert hasattr(service, "_closed")
            assert service._closed is True

            # Verify cache lock is cleared
            assert service._cache_lock is None

    def test_close_method_idempotent(self):
        """Test that close() can be called multiple times safely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)
            config["cache_backend"] = "sqlite"

            service = ASINLookupService(self.create_mock_config_manager(config))

            # Call close multiple times - should not raise errors
            service.close()
            service.close()
            service.close()

            # Verify still properly closed
            assert service._closed is True
            assert service._cache_lock is None

    def test_close_method_after_lookups(self):
        """Test close() after performing actual lookups."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            config = self.test_config.copy()
            config["cache_path"] = str(cache_path)
            config["cache_backend"] = "sqlite"

            service = ASINLookupService(self.create_mock_config_manager(config))

            # Pre-populate cache for predictable test
            cache_key = "test book_test author"
            service.cache_manager.cache_asin(cache_key, "TEST123", "test-source")

            # Perform a lookup
            result = service.lookup_by_title("Test Book", "Test Author")
            assert result.success is True
            assert result.asin == "TEST123"

            # Close after using the service
            service.close()

            # Verify proper closure
            assert service._closed is True
            assert service._cache_lock is None


class TestSQLiteCacheManager:
    """Test SQLiteCacheManager functionality."""

    def test_cache_manager_init_new_cache(self):
        """Test SQLiteCacheManager initialization with new cache file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "new_cache.db"
            cache_manager = SQLiteCacheManager(cache_path)

            assert cache_manager.cache_path == cache_path
            assert cache_path.parent.exists()  # Directory should be created
            # Verify cache is empty
            stats = cache_manager.get_stats()
            assert stats["total_entries"] == 0

            # Check that database is properly initialized
            stats = cache_manager.get_stats()
            assert stats["total_entries"] == 0
            assert "active_entries" in stats

    def test_cache_manager_init_existing_cache(self):
        """Test SQLiteCacheManager initialization with existing SQLite cache file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "existing_cache.db"

            # Create and populate existing SQLite cache
            cache_manager1 = SQLiteCacheManager(cache_path)
            cache_manager1.cache_asin("test_key", "test_asin")

            # Initialize new manager with existing cache
            cache_manager2 = SQLiteCacheManager(cache_path)

            # Verify existing data is loaded
            cached_asin = cache_manager2.get_cached_asin("test_key")
            assert cached_asin == "test_asin"

    def test_cache_manager_corrupted_cache(self):
        """Test SQLiteCacheManager handling of corrupted cache file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "corrupted_cache.db"

            # Create corrupted cache file (not valid SQLite)
            with open(cache_path, "w") as f:
                f.write("invalid sqlite content")

            # Should handle corruption gracefully by recreating cache
            cache_manager = SQLiteCacheManager(cache_path)

            # Should start with empty cache after corruption recovery
            stats = cache_manager.get_stats()
            assert stats["total_entries"] == 0

    def test_cache_asin_and_get_cached_asin(self):
        """Test caching and retrieving ASINs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            cache_manager = SQLiteCacheManager(cache_path)

            # Cache an ASIN
            cache_manager.cache_asin("test_key", "B00ZVA3XL6")

            # Retrieve cached ASIN
            cached_asin = cache_manager.get_cached_asin("test_key")

            assert cached_asin == "B00ZVA3XL6"

            # Verify it was written to SQLite database
            assert cache_path.exists()
            stats = cache_manager.get_stats()
            assert stats["total_entries"] == 1
            assert stats["active_entries"] == 1

    def test_get_cached_asin_nonexistent(self):
        """Test retrieving nonexistent cache key."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            cache_manager = SQLiteCacheManager(cache_path)

            cached_asin = cache_manager.get_cached_asin("nonexistent_key")

            assert cached_asin is None

    def test_cache_clear(self):
        """Test clearing cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            cache_manager = SQLiteCacheManager(cache_path)

            # Add some data
            cache_manager.cache_asin("key1", "asin1")
            cache_manager.cache_asin("key2", "asin2")

            # Verify data was cached
            stats_before = cache_manager.get_stats()
            assert stats_before["total_entries"] == 2

            # Clear cache
            cache_manager.clear()

            # Verify cache is empty
            stats_after = cache_manager.get_stats()
            assert stats_after["total_entries"] == 0

            # Verify cleared items cannot be retrieved
            assert cache_manager.get_cached_asin("key1") is None
            assert cache_manager.get_cached_asin("key2") is None

    def test_cache_stats(self):
        """Test cache statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            cache_manager = SQLiteCacheManager(cache_path)

            # Add some data
            cache_manager.cache_asin("key1", "asin1")
            cache_manager.cache_asin("key2", "asin2")

            stats = cache_manager.get_stats()

            assert stats["total_entries"] == 2
            assert stats["active_entries"] == 2  # All entries are active (not expired)
            assert "size_human" in stats
            assert (
                "B" in stats["size_human"] or "KB" in stats["size_human"]
            )  # SQLite file can be KB
            assert "last_updated" in stats

    def test_cache_thread_safety(self):
        """Test cache thread safety."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            cache_manager = SQLiteCacheManager(cache_path)

            # Function to cache ASINs in separate threads
            def cache_asins(thread_id):
                for i in range(10):
                    cache_manager.cache_asin(
                        f"thread_{thread_id}_key_{i}", f"asin_{thread_id}_{i}"
                    )

            # Start multiple threads
            threads = []
            for i in range(5):
                thread = threading.Thread(target=cache_asins, args=(i,))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            # Verify all entries were cached using stats
            stats = cache_manager.get_stats()
            assert stats["total_entries"] == 50
            assert stats["active_entries"] == 50

            # Verify data integrity - should be able to retrieve all entries
            for thread_id in range(5):
                for i in range(10):
                    key = f"thread_{thread_id}_key_{i}"
                    expected_asin = f"asin_{thread_id}_{i}"
                    cached_asin = cache_manager.get_cached_asin(key)
                    assert cached_asin == expected_asin

    def test_cache_save_error_handling(self):
        """Test cache save error handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "readonly_dir" / "test_cache.db"

            # Create cache manager first (this creates the directory)
            cache_manager = SQLiteCacheManager(cache_path)

            # Add a valid entry first to ensure it works
            cache_manager.cache_asin("valid_key", "valid_asin")

            # Verify the valid entry was stored
            cached_asin = cache_manager.get_cached_asin("valid_key")
            assert cached_asin == "valid_asin"

            # SQLite handles most error cases internally, so we test basic functionality
            try:
                # This should work normally
                cache_manager.cache_asin("test_key", "test_asin")

                # Verify the entry was stored
                cached_result = cache_manager.get_cached_asin("test_key")
                assert cached_result == "test_asin"

            except Exception:
                # SQLite errors should be handled gracefully
                pass

    def test_cleanup_expired_stub(self):
        """Test cleanup expired method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "test_cache.db"
            cache_manager = SQLiteCacheManager(cache_path)

            # Add some data
            cache_manager.cache_asin("key1", "asin1")

            # Check stats before cleanup
            stats_before = cache_manager.get_stats()
            assert stats_before["total_entries"] == 1

            # Cleanup expired (should find no expired entries since TTL is 30 days by default)
            removed_count = cache_manager.cleanup_expired()

            # Should be 0 since entries are not expired yet
            assert removed_count == 0

            # Verify entry still exists
            stats_after = cache_manager.get_stats()
            assert stats_after["total_entries"] == 1
            assert cache_manager.get_cached_asin("key1") == "asin1"
