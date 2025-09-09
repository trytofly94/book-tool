#!/usr/bin/env python3
"""
Test ASIN lookup functionality with real books.
"""

import sys
import tempfile
import argparse
from pathlib import Path

from datetime import datetime

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from calibre_books.core.asin_lookup import ASINLookupService  # noqa: E402
from calibre_books.core.book import BookMetadata  # noqa: E402
from calibre_books.utils.test_helpers import (  # noqa: E402
    get_test_book_path,
    get_single_book_path,
    add_book_path_argument,
)


def extract_metadata_from_epub(epub_path: Path) -> BookMetadata:
    """Extract metadata from EPUB file for testing."""
    # For testing, we'll use known metadata for Elantris
    if "elantris" in epub_path.name.lower():
        return BookMetadata(
            title="Elantris",
            author="Brandon Sanderson",
            isbn="9780765350374",  # Valid ISBN-13
            publication_date=datetime(2005, 4, 21),
        )
    elif "mistborn1" in epub_path.name.lower():
        return BookMetadata(
            title="Mistborn: The Final Empire",
            author="Brandon Sanderson",
            isbn="9780765311788",  # Valid ISBN-13
            publication_date=datetime(2006, 7, 17),
        )
    elif "weg-der-koenige" in epub_path.name.lower():
        return BookMetadata(
            title="The Way of Kings",
            author="Brandon Sanderson",
            isbn="9780765365279",  # Valid ISBN-13
            publication_date=datetime(2010, 8, 31),
        )
    else:
        # Generic metadata for testing
        return BookMetadata(
            title=epub_path.stem.replace("_", " ").title(),
            author="Brandon Sanderson",
        )


def test_single_book(book_path: Path, verbose: bool = True):
    """Test ASIN lookup for a single book."""
    print(f"\n=== Testing ASIN Lookup for: {book_path.name} ===")

    # Create temporary cache
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "test_cache.json"

        # Initialize ASIN lookup service
        config = {
            "cache_path": cache_path,
            "cache_backend": "json",  # Use JSON for testing
            "cache_ttl_days": 30,
            "sources": ["amazon", "google_books", "openlibrary"],
            "max_parallel": 1,  # Sequential for testing
        }

        service = ASINLookupService(config)

        # Extract metadata
        metadata = extract_metadata_from_epub(book_path)
        print("Extracted metadata:")
        print(f"  Title: {metadata.title}")
        print(f"  Author: {metadata.author}")
        print(f"  ISBN: {metadata.isbn}")
        print(f"  Publication Date: {metadata.publication_date}")

        # Test ASIN lookup by title/author
        print("\n--- Testing Title/Author Lookup ---")
        result = service.lookup_by_title(
            title=metadata.title, author=metadata.author, verbose=verbose
        )

        if result and result.asin:
            print(f"✅ ASIN found by title/author: {result.asin}")
            print(f"   Source: {result.source}")
            print(f"   Success: {result.success}")
        else:
            print("❌ No ASIN found by title/author")

        # Test ASIN lookup by ISBN if available
        if metadata.isbn:
            print("\n--- Testing ISBN Lookup ---")
            isbn_result = service.lookup_by_isbn(isbn=metadata.isbn, verbose=verbose)

            if isbn_result and isbn_result.asin:
                print(f"✅ ASIN found by ISBN: {isbn_result.asin}")
                print(f"   Source: {isbn_result.source}")
                print(f"   Success: {isbn_result.success}")
            else:
                print("❌ No ASIN found by ISBN")

        # Test cache functionality
        print("\n--- Testing Cache ---")
        cache_stats = service.cache_manager.get_stats()
        print(f"Cache stats: {cache_stats}")

        # Cleanup
        service.close()

        return result


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test ASIN lookup functionality with real books.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Use default book directory
  python test_asin_lookup_real_books.py

  # Use custom book directory
  python test_asin_lookup_real_books.py --book-path /custom/path/to/books

  # Use environment variable
  export CALIBRE_BOOKS_TEST_PATH=/custom/path/to/books
  python test_asin_lookup_real_books.py
""",
    )

    add_book_path_argument(parser)

    return parser.parse_args()


def main():
    """Main test function."""
    # Parse command line arguments
    args = parse_arguments()

    print("🔍 Testing ASIN Lookup with Real Books")

    # Get book directory path using the new resolution function
    try:
        book_dir = get_test_book_path(cli_args=args)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Book directory resolution failed: {e}")
        return 1

    # Test with single book first
    try:
        single_book_path = get_single_book_path(
            book_dir, "single-book-test/sanderson_elantris.epub", validate_exists=True
        )

        print(f"\n📚 Testing with: {single_book_path.name}")
        result = test_single_book(single_book_path, verbose=True)

        if result and result.asin:
            print(f"\n🎉 SUCCESS: Found ASIN {result.asin} for {single_book_path.name}")
        else:
            print(f"\n⚠️  WARNING: No ASIN found for {single_book_path.name}")
    except FileNotFoundError as e:
        print(f"❌ Test book not found: {e}")
        return 1

    # Test with a few more books
    test_books = [
        "sanderson_mistborn1_kinder-des-nebels.epub",
        "sanderson_sturmlicht1_weg-der-koenige.epub",
    ]

    for book_name in test_books:
        book_path = book_dir / book_name
        if book_path.exists():
            print(f"\n📚 Testing with: {book_name}")
            result = test_single_book(
                book_path, verbose=False
            )  # Less verbose for batch

            if result and result.asin:
                print(f"✅ SUCCESS: Found ASIN {result.asin}")
            else:
                print("❌ No ASIN found")
        else:
            print(f"⚠️  Book not found: {book_name}")

    print(f"\n📁 Book directory used: {book_dir}")

    print("\n🏁 ASIN Lookup testing completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
