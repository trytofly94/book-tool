#!/usr/bin/env python3
"""
Real-world availability check test script.

This script tests the ASIN lookup and availability checking functionality
with actual Brandon Sanderson books from the book pipeline directory.
"""

import sys
import logging
import time
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from calibre_books.core.asin_lookup import ASINLookupService  # noqa: E402
from calibre_books.core.book import Book, BookMetadata, BookFormat  # noqa: E402


@dataclass
class TestResult:
    """Result of a test run."""

    book_file: str
    title: str
    author: str
    asin_found: bool
    asin: str
    asin_source: str
    lookup_time: float
    availability_checked: bool
    availability_available: bool
    availability_metadata: dict
    error: str = None


def extract_book_info_from_filename(filename: str) -> Tuple[str, str]:
    """
    Extract book title and author from standardized filename format.

    Expected format: sanderson_title-words.epub
    """
    # Remove file extension
    name_without_ext = filename.rsplit(".", 1)[0]

    # Split by first underscore to separate author from title
    if "_" not in name_without_ext:
        return name_without_ext, "Brandon Sanderson"

    parts = name_without_ext.split("_", 1)
    author_part = parts[0]
    title_part = parts[1]

    # Clean up author
    if author_part.lower() == "sanderson":
        author = "Brandon Sanderson"
    else:
        author = author_part.replace("-", " ").title()

    # Clean up title - replace hyphens with spaces and handle German titles
    title = title_part.replace("-", " ").replace("_", " ")

    # Some title cleanup
    title_replacements = {
        "sturmlicht": "Stormlight Archive",
        "mistborn": "Mistborn",
        "skyward": "Skyward",
        "weg der koenige": "The Way of Kings",
        "pfad der winde": "Words of Radiance",
        "worte des lichts": "Oathbringer",
        "stuerme des zorns": "Rhythm of War",
        "kinder des nebels": "The Final Empire",
        "krieger des feuers": "The Well of Ascension",
        "herrscher des lichts": "The Hero of Ages",
        "ruf der sterne": "Skyward",
        "starsight": "Starsight",
        "cytonic": "Cytonic",
        "defiant": "Defiant",
        "elantris": "Elantris",
        "warbreaker": "Warbreaker",
        "sturmklaenge": "Warbreaker",
        "emperor soul": "The Emperor's Soul",
        "seele des koenigs": "The Emperor's Soul",
        "sunlit man": "The Sunlit Man",
        "herz der sonne": "The Sunlit Man",
        "tress": "Tress of the Emerald Sea",
        "smaragdgruene see": "Tress of the Emerald Sea",
    }

    title_lower = title.lower()
    for pattern, replacement in title_replacements.items():
        if pattern in title_lower:
            title = replacement
            break
    else:
        # If no specific replacement found, just capitalize
        title = " ".join(word.capitalize() for word in title.split())

    return title, author


def setup_logging():
    """Set up logging for the test script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("availability_test.log"),
        ],
    )

    # Reduce noise from other loggers
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def create_book_from_file(file_path: Path) -> Book:
    """Create a Book object from a file path."""
    title, author = extract_book_info_from_filename(file_path.name)

    # Determine format from file extension
    format_str = file_path.suffix.lower().lstrip(".")
    try:
        book_format = BookFormat(format_str)
    except ValueError:
        book_format = BookFormat.EPUB  # Default fallback

    metadata = BookMetadata(title=title, author=author, format=book_format)

    return Book(metadata=metadata, file_path=file_path)


def test_asin_lookup_and_availability(books_dir: Path) -> List[TestResult]:
    """
    Test ASIN lookup and availability checking for all books in the directory.

    Args:
        books_dir: Path to directory containing book files

    Returns:
        List of test results
    """
    logger = logging.getLogger(__name__)

    # Initialize config manager (mock for testing)
    config = {
        "cache_path": "~/.book-tool/test_cache.json",
        "sources": ["amazon", "google-books", "openlibrary"],
        "rate_limit": 1.0,  # Slower rate limit for real testing
    }

    class MockConfigManager:
        def get_asin_config(self):
            return config

    config_manager = MockConfigManager()

    # Initialize ASIN lookup service
    asin_service = ASINLookupService(config_manager)

    # Find all book files
    book_files = []
    for ext in ["*.epub", "*.mobi", "*.azw", "*.azw3", "*.pdf"]:
        book_files.extend(books_dir.glob(ext))

    logger.info(f"Found {len(book_files)} book files to test")

    results = []

    for i, book_file in enumerate(book_files, 1):
        logger.info(f"\n=== Testing {i}/{len(book_files)}: {book_file.name} ===")

        try:
            # Create book object
            book = create_book_from_file(book_file)
            logger.info(
                f"Extracted metadata: Title='{book.title}', Author='{book.author}'"
            )

            # Perform ASIN lookup
            start_time = time.time()
            lookup_result = asin_service.lookup_by_title(
                book.title,
                author=book.author,
                verbose=True,  # Enable verbose logging for debugging
            )
            lookup_time = time.time() - start_time

            logger.info(f"ASIN lookup completed in {lookup_time:.2f}s")
            logger.info(
                f"Success: {lookup_result.success}, ASIN: {lookup_result.asin}, Source: {lookup_result.source}"
            )

            if lookup_result.error:
                logger.warning(f"Lookup error: {lookup_result.error}")

            # Initialize test result
            test_result = TestResult(
                book_file=book_file.name,
                title=book.title,
                author=book.author,
                asin_found=lookup_result.success,
                asin=lookup_result.asin or "",
                asin_source=lookup_result.source or "",
                lookup_time=lookup_time,
                availability_checked=False,
                availability_available=False,
                availability_metadata={},
            )

            # If we found an ASIN, check availability
            if lookup_result.success and lookup_result.asin:
                logger.info(f"Checking availability for ASIN: {lookup_result.asin}")
                try:
                    availability = asin_service.check_availability(lookup_result.asin)

                    test_result.availability_checked = True
                    test_result.availability_available = availability.available
                    test_result.availability_metadata = availability.metadata or {}

                    logger.info(
                        f"Availability check: Available={availability.available}"
                    )
                    logger.info(f"Availability metadata: {availability.metadata}")

                except Exception as e:
                    logger.error(f"Availability check failed: {e}")
                    test_result.error = f"Availability check error: {str(e)}"
            else:
                logger.info("Skipping availability check - no ASIN found")
                test_result.error = lookup_result.error

            results.append(test_result)

        except Exception as e:
            logger.error(f"Test failed for {book_file.name}: {e}", exc_info=True)
            results.append(
                TestResult(
                    book_file=book_file.name,
                    title="ERROR",
                    author="ERROR",
                    asin_found=False,
                    asin="",
                    asin_source="",
                    lookup_time=0.0,
                    availability_checked=False,
                    availability_available=False,
                    availability_metadata={},
                    error=str(e),
                )
            )

        # Rate limiting between tests
        time.sleep(2.0)

    return results


def print_test_summary(results: List[TestResult]):
    """Print a summary of all test results."""
    logger = logging.getLogger(__name__)

    total_tests = len(results)
    successful_lookups = sum(1 for r in results if r.asin_found)
    availability_checks = sum(1 for r in results if r.availability_checked)
    available_books = sum(1 for r in results if r.availability_available)
    errors = sum(1 for r in results if r.error)

    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total books tested: {total_tests}")
    logger.info(
        f"Successful ASIN lookups: {successful_lookups} ({successful_lookups / total_tests * 100:.1f}%)"
    )
    logger.info(f"Availability checks performed: {availability_checks}")
    logger.info(
        f"Books available on Amazon: {available_books} ({available_books / availability_checks * 100:.1f}% of checked)"
    )
    logger.info(f"Tests with errors: {errors}")

    # Average lookup time
    successful_times = [r.lookup_time for r in results if r.asin_found]
    if successful_times:
        avg_time = sum(successful_times) / len(successful_times)
        logger.info(f"Average successful lookup time: {avg_time:.2f}s")

    logger.info("\nDETAILED RESULTS:")
    logger.info("-" * 100)
    logger.info(
        f"{'File':<35} {'Title':<25} {'ASIN':<12} {'Source':<15} {'Available':<10} {'Time':<6}"
    )
    logger.info("-" * 100)

    for result in results:
        availability_str = (
            "Yes"
            if result.availability_available
            else "No" if result.availability_checked else "N/A"
        )
        if result.error:
            availability_str = "ERROR"

        logger.info(
            f"{result.book_file:<35} {result.title[:24]:<25} {result.asin:<12} {result.asin_source:<15} {availability_str:<10} {result.lookup_time:.2f}s"
        )

    # Show errors if any
    if errors > 0:
        logger.info(f"\nERRORS ({errors}):")
        for result in results:
            if result.error:
                logger.info(f"  {result.book_file}: {result.error}")


def main():
    """Main test function."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Path to the book pipeline directory
    books_dir = Path("/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/")

    if not books_dir.exists():
        logger.error(f"Books directory not found: {books_dir}")
        sys.exit(1)

    logger.info("Starting real-world ASIN lookup and availability check test")
    logger.info(f"Books directory: {books_dir}")

    # Run the tests
    start_time = time.time()
    results = test_asin_lookup_and_availability(books_dir)
    total_time = time.time() - start_time

    # Print summary
    print_test_summary(results)

    logger.info(f"\nTotal test duration: {total_time:.2f}s")
    logger.info("Test completed!")


if __name__ == "__main__":
    main()
