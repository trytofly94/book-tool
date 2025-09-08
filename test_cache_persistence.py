#!/usr/bin/env python3
"""
Test cache persistence between runs for Issue #39.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import after path modification
from calibre_books.core.asin_lookup import ASINLookupService  # noqa: E402


def create_mock_config_manager():
    """Create mock config manager with persistent cache."""
    cache_path = Path("/tmp/book_tool_integration_test_cache.db")
    mock_config = Mock()
    mock_config.get_asin_config.return_value = {
        "cache_path": str(cache_path),
        "sources": ["amazon", "goodreads", "openlibrary"],
        "rate_limit": 0.1,
    }
    return mock_config


def main():
    print("🔄 Testing Cache Persistence")
    print("=" * 40)

    mock_config = create_mock_config_manager()
    service = ASINLookupService(mock_config)

    # Test with one book
    print("🔍 Looking up: The Way of Kings by Brandon Sanderson")
    result = service.lookup_by_title("The Way of Kings", author="Brandon Sanderson")

    print(f"   Result: {result.success}")
    print(f"   ASIN: {result.asin}")
    print(f"   Source: {result.source}")
    print(f"   From Cache: {result.from_cache}")

    # Show cache stats
    cache_stats = service.cache_manager.get_stats()
    print("\n💾 Cache Stats:")
    print(f"   Total Entries: {cache_stats['total_entries']}")
    print(f"   Hits: {cache_stats['hits']}")
    print(f"   Misses: {cache_stats['misses']}")
    print(f"   Hit Rate: {cache_stats['hit_rate']}%")

    service.cache_manager.close()
    print("\n✅ Cache persisted to:", service.cache_path)
    print("🚀 Run this script again to test cache hits!")


if __name__ == "__main__":
    main()
