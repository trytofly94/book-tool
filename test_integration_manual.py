#!/usr/bin/env python3
"""
Manual integration test for Issue #39 - Test ASIN lookup with real books from book-pipeline.
This tests the SQLiteCacheManager and ASINLookupService with actual Sanderson books.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import after path modification
from calibre_books.core.asin_lookup import ASINLookupService  # noqa: E402
from calibre_books.core.cache import SQLiteCacheManager  # noqa: E402


def create_mock_config_manager(cache_dir: Path):
    """Create mock config manager for testing."""
    mock_config = Mock()
    mock_config.get_asin_config.return_value = {
        "cache_path": str(cache_dir / "integration_test_cache.db"),
        "sources": ["amazon", "goodreads", "openlibrary"],
        "rate_limit": 0.1,  # Fast for testing
    }
    return mock_config


def test_sanderson_books():
    """Test ASIN lookup with known Brandon Sanderson books."""
    print("🚀 Starting Integration Test for Issue #39")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir)
        mock_config = create_mock_config_manager(cache_dir)

        # Initialize ASIN lookup service
        print("📊 Initializing ASINLookupService with SQLiteCacheManager...")
        service = ASINLookupService(mock_config)

        # Test cache manager type
        print(f"✅ Cache Manager Type: {type(service.cache_manager).__name__}")
        assert isinstance(service.cache_manager, SQLiteCacheManager)

        # Test books from the book-pipeline collection
        test_books = [
            ("The Way of Kings", "Brandon Sanderson"),
            ("Words of Radiance", "Brandon Sanderson"),
            ("Elantris", "Brandon Sanderson"),
            ("Mistborn: The Final Empire", "Brandon Sanderson"),
        ]

        print("\n📚 Testing ASIN Lookups:")
        print("-" * 40)

        results = []
        for title, author in test_books:
            print(f"🔍 Looking up: {title} by {author}")

            try:
                result = service.lookup_by_title(title, author=author, verbose=True)
                print(f"   Result: {result.success}")
                if result.success:
                    print(f"   ASIN: {result.asin}")
                    print(f"   Source: {result.source}")
                    print(f"   From Cache: {result.from_cache}")
                else:
                    print(f"   Error: {result.error}")

                results.append(result)
                print()

            except Exception as e:
                print(f"   ❌ Exception: {e}")
                results.append(None)
                print()

        # Test cache functionality
        print("💾 Testing Cache Functionality:")
        print("-" * 30)

        cache_stats = service.cache_manager.get_stats()
        print(f"   Total Entries: {cache_stats['total_entries']}")
        print(f"   Active Entries: {cache_stats['active_entries']}")
        print(f"   Hit Rate: {cache_stats['hit_rate']}%")
        print(f"   Hits: {cache_stats['hits']}")
        print(f"   Misses: {cache_stats['misses']}")
        print(f"   Writes: {cache_stats['writes']}")

        # Test cache retrieval
        if results and results[0] and results[0].success:
            print(f"\n🔄 Testing Cache Retrieval for '{test_books[0][0]}':")
            cache_key = f"{test_books[0][0].lower()}_{test_books[0][1].lower()}"
            cached_asin = service.cache_manager.get_cached_asin(cache_key)
            print(f"   Cached ASIN: {cached_asin}")

        print("\n📊 Final Statistics:")
        print("-" * 20)
        successful_lookups = sum(1 for r in results if r and r.success)
        print(f"   Successful Lookups: {successful_lookups}/{len(test_books)}")
        print(f"   Cache File Size: {cache_stats['size_human']}")

        # Close cache manager
        service.cache_manager.close()

        print("\n✅ Integration Test Completed Successfully!")
        return successful_lookups


if __name__ == "__main__":
    test_sanderson_books()
