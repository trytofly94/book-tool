#!/usr/bin/env python3
"""
Comprehensive test suite for ASINLookupService.close() method.
Tests the new close() method implementation for Issue #66.
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Import needs to be after path modification
from calibre_books.core.asin_lookup import ASINLookupService  # noqa: E402


def setup_test_service(temp_db_path=None):
    """Setup a test ASIN lookup service."""
    if temp_db_path is None:
        temp_db_path = tempfile.mktemp(suffix=".db")

    config = {
        "cache_path": Path(temp_db_path),
        "cache_backend": "sqlite",  # Use SQLite for testing
        "cache_ttl_days": 30,
        "sources": ["amazon", "google_books", "openlibrary"],
        "max_parallel": 1,  # Sequential for testing
    }

    service = ASINLookupService(config)
    return service, temp_db_path


def test_basic_close():
    """Test basic close() functionality."""
    print("=== Test 1: Basic close() functionality ===")

    service, temp_db = setup_test_service()

    # Verify service is functional before close
    assert hasattr(service, "cache_manager")
    assert hasattr(service, "_cache_lock")

    # Test close
    service.close()

    # Verify _closed flag is set
    assert hasattr(service, "_closed")
    assert service._closed is True

    # Verify cache lock is cleared
    assert service._cache_lock is None

    print("✅ Basic close() test passed")

    # Cleanup
    if os.path.exists(temp_db):
        os.remove(temp_db)


def test_idempotent_close():
    """Test that close() can be called multiple times safely."""
    print("\n=== Test 2: Idempotent close() ===")

    service, temp_db = setup_test_service()

    # Call close multiple times
    service.close()
    print("First close() called")

    service.close()  # Should not raise any errors
    print("Second close() called")

    service.close()  # Should not raise any errors
    print("Third close() called")

    # Verify still marked as closed
    assert service._closed is True

    print("✅ Idempotent close() test passed")

    # Cleanup
    if os.path.exists(temp_db):
        os.remove(temp_db)


def test_close_with_actual_lookup():
    """Test close() after performing actual ASIN lookups."""
    print("\n=== Test 3: Close after actual ASIN lookups ===")

    service, temp_db = setup_test_service()

    # Perform a simple lookup to initialize internal state
    try:
        result = service.lookup_by_title("Test Book", "Test Author")
        print(f"Lookup result: {result.asin if result.success else 'No ASIN found'}")
    except Exception as e:
        print(f"Lookup failed (expected): {e}")

    # Now close the service
    service.close()

    # Verify closure
    assert service._closed is True
    assert service._cache_lock is None

    print("✅ Close after lookup test passed")

    # Cleanup
    if os.path.exists(temp_db):
        os.remove(temp_db)


def test_close_with_cache_operations():
    """Test close() with cache operations."""
    print("\n=== Test 4: Close with cache operations ===")

    service, temp_db = setup_test_service()

    # Get cache stats to ensure cache is working
    try:
        stats = service.get_cache_stats()
        print(f"Cache stats before close: {stats}")
    except Exception as e:
        print(f"Cache stats failed: {e}")

    # Close the service
    service.close()

    # Verify closure
    assert service._closed is True

    print("✅ Close with cache operations test passed")

    # Cleanup
    if os.path.exists(temp_db):
        os.remove(temp_db)


def test_close_without_cache_manager():
    """Test close() when cache_manager doesn't have close() method (edge case)."""
    print("\n=== Test 5: Close without cache manager close() method ===")

    service, temp_db = setup_test_service()

    # Mock a cache manager without close() method
    class MockCacheManager:
        def get_stats(self):
            return {}

    service.cache_manager = MockCacheManager()

    # Should not raise error even if cache manager has no close()
    service.close()

    # Verify closure
    assert service._closed is True

    print("✅ Close without cache manager close() test passed")

    # Cleanup
    if os.path.exists(temp_db):
        os.remove(temp_db)


def test_batch_books_close():
    """Test close() with batch processing of real books."""
    print("\n=== Test 6: Close with batch processing ===")

    # Check if test books directory exists
    books_dir = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
    if not os.path.exists(books_dir):
        print(f"⚠️ Skipping batch test - books directory not found: {books_dir}")
        return

    service, temp_db = setup_test_service()

    # Find some test books
    epub_files = list(Path(books_dir).glob("*.epub"))[:2]  # Test with first 2 books

    if not epub_files:
        print("⚠️ No EPUB files found for batch testing")
        service.close()
        if os.path.exists(temp_db):
            os.remove(temp_db)
        return

    print(f"Testing with {len(epub_files)} books")

    # Process books (this would use threading internally)
    for book_path in epub_files:
        try:
            # Just test that we can create the service and close it
            # after potential threading operations
            print(f"Processing: {book_path.name}")

            # Simulate what the real test script does
            result = service.lookup_by_title(book_path.stem, "Test Author")
            print(f"  Result: {result.asin if result.success else 'No ASIN'}")

        except Exception as e:
            print(f"  Error processing {book_path.name}: {e}")

    # Close after batch operations
    service.close()

    # Verify closure
    assert service._closed is True

    print("✅ Batch books close test passed")

    # Cleanup
    if os.path.exists(temp_db):
        os.remove(temp_db)


def main():
    """Run all close() method tests."""
    print("🧪 Testing ASINLookupService.close() method implementation")
    print("=" * 60)

    # Setup logging to see debug messages
    logging.basicConfig(level=logging.INFO)

    try:
        test_basic_close()
        test_idempotent_close()
        test_close_with_actual_lookup()
        test_close_with_cache_operations()
        test_close_without_cache_manager()
        test_batch_books_close()

        print("\n🎉 All close() method tests passed!")
        print("✅ Issue #66 implementation is working correctly")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
