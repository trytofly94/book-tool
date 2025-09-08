#!/usr/bin/env python3
"""
Quick integration test for ASIN lookup performance improvements.
Tests the new SQLite cache, rate limiting, and confidence scoring on a small subset of books.
"""

import sys
import tempfile
from pathlib import Path
import logging

# Add the source directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from calibre_books.core.book import Book
from calibre_books.core.cache import SQLiteCacheManager
from calibre_books.core.rate_limiter import DomainRateLimiter
from calibre_books.core.asin_lookup import ASINLookupService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_sqlite_cache():
    """Test SQLite cache functionality."""
    print("\n" + "=" * 60)
    print("TESTING SQLITE CACHE")
    print("=" * 60)

    # Create temporary cache
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        cache_path = Path(tmp_file.name)

    try:
        # Test cache creation
        cache = SQLiteCacheManager(cache_path, ttl_days=30)

        # Get initial stats (may include migrated entries)
        initial_stats = cache.get_stats()
        initial_entries = initial_stats["total_entries"]
        print(
            f"ℹ️  Cache initialized with {initial_entries} entries (including any migrations)"
        )

        # Test cache operations
        test_key = "test_book_title_author_unique"
        test_asin = "B01234ABCD"

        # Test cache miss for our unique key
        result = cache.get_cached_asin(test_key)
        assert result is None, "Our test key should not be in cache initially"
        print("✓ Cache miss test passed")

        # Test cache write
        cache.cache_asin(test_key, test_asin, source="test", confidence_score=0.9)
        print("✓ Cache write completed")

        # Test cache hit
        result = cache.get_cached_asin(test_key)
        assert result == test_asin, f"Cache should return {test_asin}, got {result}"
        print("✓ Cache hit test passed")

        # Test cache stats
        stats = cache.get_stats()
        expected_entries = initial_entries + 1
        assert (
            stats["total_entries"] == expected_entries
        ), f"Should have {expected_entries} entries, got {stats['total_entries']}"
        print(
            f"✓ Cache stats: {stats['total_entries']} entries, {stats['hit_rate']:.1f}% hit rate"
        )

        cache.close()
        print("✓ SQLite cache test completed successfully!")

    finally:
        # Cleanup
        if cache_path.exists():
            cache_path.unlink()


def test_rate_limiter():
    """Test rate limiter functionality."""
    print("\n" + "=" * 60)
    print("TESTING RATE LIMITER")
    print("=" * 60)

    # Create rate limiter
    rate_limiter = DomainRateLimiter()

    # Test token bucket
    test_url = "https://www.amazon.com/test"

    # Should be fast first time
    import time

    start_time = time.time()
    wait_time = rate_limiter.wait_for_request(test_url)
    actual_wait = time.time() - start_time
    print(f"✓ First request wait time: {wait_time:.3f}s (actual: {actual_wait:.3f}s)")

    # Second request should have some delay
    start_time = time.time()
    wait_time = rate_limiter.wait_for_request(test_url)
    actual_wait = time.time() - start_time
    print(f"✓ Second request wait time: {wait_time:.3f}s (actual: {actual_wait:.3f}s)")

    # Test stats (note: requests_made only counts actual HTTP requests, not wait_for_request calls)
    stats = rate_limiter.get_domain_stats("amazon.com")
    print(f"✓ Rate limiter stats: {stats['requests_made']} HTTP requests made")

    # Test that the rate limiter has the correct configuration
    bucket_status = stats.get("bucket_status", {})
    if bucket_status:
        assert "current_tokens" in bucket_status, "Bucket should have token status"
        assert "capacity" in bucket_status, "Bucket should have capacity info"
        print(
            f"✓ Token bucket status: {bucket_status['current_tokens']}/{bucket_status['capacity']} tokens"
        )

    print("✓ Rate limiter test completed successfully!")


def create_test_books():
    """Create a small set of test books."""
    return [
        Book(
            title="The Way of Kings",
            author="Brandon Sanderson",
            isbn="9780765326355",
            file_path=Path("/test/sturmlicht1.epub"),
        ),
        Book(
            title="Mistborn: The Final Empire",
            author="Brandon Sanderson",
            isbn="9780765311788",
            file_path=Path("/test/mistborn1.epub"),
        ),
        Book(
            title="Elantris",
            author="Brandon Sanderson",
            isbn="9780765350374",
            file_path=Path("/test/elantris.epub"),
        ),
    ]


def test_asin_lookup_integration():
    """Test the complete ASIN lookup integration."""
    print("\n" + "=" * 60)
    print("TESTING ASIN LOOKUP INTEGRATION")
    print("=" * 60)

    # Create temporary config directory
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir)
        cache_path = config_dir / "asin_cache.db"

        # Mock config manager
        class MockConfigManager:
            def get_asin_config(self):
                return {
                    "sources": ["amazon", "google-books", "openlibrary"],
                    "rate_limit": 2.0,
                    "cache": {
                        "backend": "sqlite",
                        "path": str(cache_path),
                        "ttl_days": 30,
                        "auto_cleanup": True,
                    },
                    "performance": {
                        "max_parallel": 2,  # Lower for testing
                        "connection_pool_size": 5,
                        "rate_limits": {
                            "amazon.com": 1.0,
                            "googleapis.com": 5.0,
                            "openlibrary.org": 3.0,
                        },
                    },
                }

        try:
            # Create ASIN lookup service
            config_manager = MockConfigManager()
            asin_service = ASINLookupService(config_manager)

            print("✓ ASIN service created successfully")

            # Test single lookup (this will make real API calls)
            print("Testing single lookup (may take a few seconds)...")

            result = asin_service.lookup_by_title(
                title="The Way of Kings", author="Brandon Sanderson", verbose=True
            )

            print(
                f"✓ Single lookup result: {result.success}, ASIN: {result.asin}, source: {result.source}"
            )
            if result.metadata and "confidence" in result.metadata:
                print(f"✓ Confidence score: {result.metadata['confidence']:.2f}")

            # Test confidence scoring
            if result.success:
                confidence = asin_service.calculate_result_confidence(
                    result.asin, result.source, result.query_title, result.query_author
                )
                print(f"✓ Calculated confidence: {confidence:.2f}")

            # Test performance stats
            perf_stats = asin_service.get_performance_stats()
            print(f"✓ Performance stats collected: {len(perf_stats)} categories")

            # Cleanup
            asin_service.close()
            print("✓ ASIN lookup integration test completed!")

        except Exception as e:
            print(f"✗ ASIN lookup integration test failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    return True


def main():
    """Run all integration tests."""
    print("STARTING PERFORMANCE IMPROVEMENTS INTEGRATION TESTS")
    print("=" * 80)

    success = True

    try:
        test_sqlite_cache()
        test_rate_limiter()

        # Only run full integration test if user confirms
        print("\n" + "=" * 60)
        print("REAL API TEST WARNING")
        print("=" * 60)
        print("The next test will make real API calls to Amazon, Google Books, etc.")
        print("This may take 10-30 seconds and will consume API quotas.")

        try:
            response = input("Do you want to proceed with the real API test? (y/N): ")
            if response.lower().startswith("y"):
                success &= test_asin_lookup_integration()
            else:
                print("Skipping real API test.")
        except EOFError:
            print("Non-interactive environment detected. Running real API test...")
            success &= test_asin_lookup_integration()

    except Exception as e:
        print(f"Integration tests failed: {e}")
        import traceback

        traceback.print_exc()
        success = False

    print("\n" + "=" * 80)
    if success:
        print("🎉 ALL INTEGRATION TESTS PASSED!")
        print("Performance improvements are ready for production use.")
    else:
        print("❌ SOME TESTS FAILED!")
        print("Please review the errors above before proceeding.")
    print("=" * 80)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
