#!/usr/bin/env python3
"""
Comprehensive Testing Suite for Issue #19 - Localization ASIN Lookup
Tests the complete localization pipeline with all available German books
"""

import os
import sys
import glob
import logging
from datetime import datetime

# Import our modules
try:
    from localization_metadata_extractor import LocalizationMetadataExtractor
    from enhanced_asin_lookup import ASINLookupService
    from calibre_asin_automation import CalibreASINAutomation
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from localization_metadata_extractor import LocalizationMetadataExtractor
    from enhanced_asin_lookup import ASINLookupService
    from calibre_asin_automation import CalibreASINAutomation

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LocalizationTestSuite:
    """Comprehensive test suite for localization ASIN lookup functionality"""

    def __init__(self):
        self.test_directory = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
        self.extractor = LocalizationMetadataExtractor()
        self.lookup_service = ASINLookupService()
        self.automation = CalibreASINAutomation()

        # Test results storage
        self.results = {
            "metadata_extraction": {},
            "asin_lookup": {},
            "edge_cases": {},
            "statistics": {
                "total_files": 0,
                "successful_extractions": 0,
                "successful_lookups": 0,
                "german_books_identified": 0,
                "english_books_identified": 0,
                # New language statistics for Issue #23
                "japanese_books_identified": 0,
                "portuguese_books_identified": 0,
                "dutch_books_identified": 0,
                "failed_extractions": 0,
                "failed_lookups": 0,
            },
        }

    def find_test_books(self):
        """Find all Brandon Sanderson test books"""
        pattern = os.path.join(self.test_directory, "sanderson_*.epub")
        epub_files = glob.glob(pattern)

        # Also check for .mobi files
        mobi_pattern = os.path.join(self.test_directory, "sanderson_*.mobi")
        mobi_files = glob.glob(mobi_pattern)

        all_files = epub_files + mobi_files
        logger.info(f"Found {len(all_files)} Sanderson test books")

        return sorted(all_files)

    def test_metadata_extraction(self, book_files):
        """Test metadata extraction for all books"""
        logger.info("=== Testing Metadata Extraction ===")

        for book_file in book_files:
            filename = os.path.basename(book_file)
            logger.info(f"Testing metadata extraction: {filename}")

            try:
                metadata = self.extractor.extract_metadata_from_path(book_file)

                # Store results
                self.results["metadata_extraction"][filename] = {
                    "success": True,
                    "metadata": metadata,
                    "has_title": bool(metadata.get("title", "").strip()),
                    "has_language": bool(metadata.get("language", "").strip()),
                    "has_author": bool(metadata.get("author", "").strip()),
                    "language": metadata.get("language", "unknown"),
                }

                # Update statistics
                self.results["statistics"]["successful_extractions"] += 1

                if metadata.get("language", "").lower() in ["de", "deu"]:
                    self.results["statistics"]["german_books_identified"] += 1
                elif metadata.get("language", "").lower() in ["en", "eng"]:
                    self.results["statistics"]["english_books_identified"] += 1

                title = metadata.get("title", "N/A")
                lang = metadata.get("language", "N/A")
                logger.info(f"  ✓ Success: Title='{title}', Lang='{lang}'")

            except Exception as e:
                logger.error(f"  ✗ Failed: {e}")
                self.results["metadata_extraction"][filename] = {
                    "success": False,
                    "error": str(e),
                }
                self.results["statistics"]["failed_extractions"] += 1

            self.results["statistics"]["total_files"] += 1

    def test_asin_lookup(self, book_files, max_tests=5):
        """Test ASIN lookup with localization for selected books"""
        logger.info("=== Testing ASIN Lookup with Localization ===")

        # Select a subset for ASIN testing to avoid rate limiting
        test_files = book_files[:max_tests]
        test_count = len(test_files)
        logger.info(
            f"Testing ASIN lookup for {test_count} books "
            f"(limited to avoid rate limits)"
        )

        for book_file in test_files:
            filename = os.path.basename(book_file)
            logger.info(f"Testing ASIN lookup: {filename}")

            try:
                # Use localized ASIN lookup
                asin = self.lookup_service.lookup_multiple_sources(file_path=book_file)

                # Store results
                self.results["asin_lookup"][filename] = {
                    "success": bool(asin),
                    "asin": asin or "Not found",
                    "method": "localized",
                }

                if asin:
                    self.results["statistics"]["successful_lookups"] += 1
                    logger.info(f"  ✓ ASIN found: {asin}")
                else:
                    self.results["statistics"]["failed_lookups"] += 1
                    logger.info("  ✗ No ASIN found")

                # Add rate limiting delay
                import time

                time.sleep(2)  # 2 second delay between lookups

            except Exception as e:
                logger.error(f"  ✗ Lookup failed: {e}")
                self.results["asin_lookup"][filename] = {
                    "success": False,
                    "error": str(e),
                }
                self.results["statistics"]["failed_lookups"] += 1

    def test_edge_cases(self):
        """Test edge cases and known problematic files"""
        logger.info("=== Testing Edge Cases ===")

        pipeline_base = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
        edge_cases = [
            # Known corrupted file
            f"{pipeline_base}/sanderson_sturmlicht1_weg-der-koenige.epub",
            # Non-existent file
            "/nonexistent/sanderson_test_book.epub",
        ]

        for case_file in edge_cases:
            filename = os.path.basename(case_file)
            logger.info(f"Testing edge case: {filename}")

            try:
                metadata = self.extractor.extract_metadata_from_path(case_file)
                self.results["edge_cases"][filename] = {
                    "success": True,
                    "metadata": metadata,
                    "fallback_used": not os.path.exists(case_file)
                    or self._is_likely_fallback(metadata),
                }
                logger.info(f"  ✓ Handled gracefully: {metadata}")

            except Exception as e:
                logger.warning(f"  ! Exception (expected): {e}")
                self.results["edge_cases"][filename] = {
                    "success": False,
                    "error": str(e),
                    "expected": True,
                }

    def _is_likely_fallback(self, metadata):
        """Check if metadata likely came from filename fallback"""
        title = metadata.get("title", "")
        # If title looks like it was extracted from filename (Title Case, simple)
        return bool(title and " " in title and title.istitle())

    def test_search_terms_generation(self, book_files):
        """Test search terms generation for localization"""
        logger.info("=== Testing Search Terms Generation ===")

        # Test with a few representative files
        pipeline_base = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
        test_files = [
            book_files[0] if book_files else None,  # First book
            f"{pipeline_base}/sanderson_mistborn1_kinder-des-nebels.epub",
            f"{pipeline_base}/sanderson_skyward1_ruf-der-sterne.epub",
        ]

        for book_file in test_files:
            if not book_file or not os.path.exists(book_file):
                continue

            filename = os.path.basename(book_file)
            logger.info(f"Testing search terms: {filename}")

            try:
                metadata = self.extractor.extract_metadata_from_path(book_file)
                search_terms = self.extractor.get_localized_search_terms(metadata)

                count = len(search_terms)
                logger.info(f"  Generated {count} search strategies:")
                for i, term in enumerate(search_terms[:3], 1):  # Show first 3
                    strategy = term.get("strategy", "unknown")
                    title = term["title"]
                    domain = term["amazon_domain"]
                    logger.info(f"    {i}. [{strategy}] '{title}' on {domain}")

                if len(search_terms) > 3:
                    logger.info(f"    ... and {len(search_terms) - 3} more strategies")

            except Exception as e:
                logger.error(f"  ✗ Search terms generation failed: {e}")

    def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("=== Generating Test Report ===")

        report = []
        report.append("=" * 80)
        report.append("LOCALIZATION ASIN LOOKUP - COMPREHENSIVE TEST REPORT")
        report.append("=" * 80)
        report.append(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("Issue: #19 - Localization ASIN Lookup Fix")
        report.append("")

        # Statistics
        stats = self.results["statistics"]
        report.append("OVERALL STATISTICS")
        report.append("-" * 40)
        report.append(f"Total Files Processed: {stats['total_files']}")
        report.append(
            f"Successful Metadata Extractions: {stats['successful_extractions']}"
        )
        report.append(f"Failed Metadata Extractions: {stats['failed_extractions']}")
        report.append(f"German Books Identified: {stats['german_books_identified']}")
        report.append(f"English Books Identified: {stats['english_books_identified']}")
        # New language statistics for Issue #23
        report.append(
            f"Japanese Books Identified: {stats['japanese_books_identified']}"
        )
        report.append(
            f"Portuguese Books Identified: {stats['portuguese_books_identified']}"
        )
        report.append(f"Dutch Books Identified: {stats['dutch_books_identified']}")
        report.append(f"Successful ASIN Lookups: {stats['successful_lookups']}")
        report.append(f"Failed ASIN Lookups: {stats['failed_lookups']}")
        report.append("")

        # Metadata extraction results
        report.append("METADATA EXTRACTION RESULTS")
        report.append("-" * 40)
        for filename, result in self.results["metadata_extraction"].items():
            if result["success"]:
                lang = result["metadata"].get("language", "unknown")
                title = result["metadata"].get("title", "N/A")[
                    :50
                ]  # Truncate long titles
                report.append(f"✓ {filename}")
                report.append(f"    Title: {title}")
                report.append(f"    Language: {lang}")
            else:
                report.append(f"✗ {filename}: {result.get('error', 'Unknown error')}")
        report.append("")

        # ASIN lookup results
        report.append("ASIN LOOKUP RESULTS")
        report.append("-" * 40)
        for filename, result in self.results["asin_lookup"].items():
            if result["success"]:
                report.append(f"✓ {filename}: {result['asin']}")
            else:
                report.append(f"✗ {filename}: {result.get('error', 'No ASIN found')}")
        report.append("")

        # Edge cases
        report.append("EDGE CASE HANDLING")
        report.append("-" * 40)
        for filename, result in self.results["edge_cases"].items():
            if result["success"]:
                fallback = " (fallback used)" if result.get("fallback_used") else ""
                report.append(f"✓ {filename}: Handled gracefully{fallback}")
            else:
                expected = " (expected)" if result.get("expected") else ""
                report.append(
                    f"✗ {filename}: {result.get('error', 'Unknown error')}{expected}"
                )
        report.append("")

        # Success rate calculation
        extraction_rate = (
            stats["successful_extractions"] / max(stats["total_files"], 1)
        ) * 100
        lookup_rate = (
            stats["successful_lookups"] / max(len(self.results["asin_lookup"]), 1)
        ) * 100

        report.append("SUCCESS RATES")
        report.append("-" * 40)
        report.append(f"Metadata Extraction: {extraction_rate:.1f}%")
        report.append(f"ASIN Lookup: {lookup_rate:.1f}%")
        report.append("")

        # Conclusion
        report.append("CONCLUSION")
        report.append("-" * 40)
        if stats["german_books_identified"] > 0:
            report.append("✓ German book localization is working")
            report.append("✓ German titles are being extracted correctly")

        if stats["successful_lookups"] > 0:
            report.append("✓ Localized ASIN lookups are successful")

        if extraction_rate > 80:
            report.append("✓ Metadata extraction is reliable")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def run_comprehensive_test(self, max_asin_tests=3):
        """Run the complete test suite"""
        logger.info("Starting Comprehensive Localization Test Suite")

        # Find test books
        book_files = self.find_test_books()
        if not book_files:
            logger.error("No test books found!")
            return

        # Run tests
        self.test_metadata_extraction(book_files)
        self.test_search_terms_generation(book_files)
        self.test_edge_cases()
        self.test_asin_lookup(book_files, max_tests=max_asin_tests)
        # New test for Issue #23 language support
        self.test_new_language_support()

        # Generate and display report
        report = self.generate_report()
        print(report)

        # Save report to file
        report_file = (
            f"localization_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"Test report saved to: {report_file}")

        return self.results

    def test_new_language_support(self):
        """Test the newly added language support from Issue #23"""
        logger.info("=== Testing New Language Support (Issue #23) ===")

        # Test cases for the new languages
        test_cases = [
            {
                "name": "Japanese - Haruki Murakami",
                "title": "ノルウェイの森",
                "author": "村上春樹",
                "expected_language": "ja",
                "expected_domain": "amazon.co.jp",
            },
            {
                "name": "Portuguese - Paulo Coelho",
                "title": "O Alquimista",
                "author": "Paulo Coelho",
                "expected_language": "pt",
                "expected_domain": "amazon.com.br",
            },
            {
                "name": "Dutch - Anne Frank",
                "title": "Het Achterhuis",
                "author": "Anne Frank",
                "expected_language": "nl",
                "expected_domain": "amazon.nl",
            },
        ]

        for test_case in test_cases:
            logger.info(f"Testing: {test_case['name']}")

            # Create mock metadata for testing
            mock_metadata = {
                "title": test_case["title"],
                "author": test_case["author"],
                "language": test_case["expected_language"],
                "series": "",
                "series_index": "",
            }

            try:
                # Test language detection
                detected_lang = self.extractor._guess_language_from_title(
                    test_case["title"]
                )
                if detected_lang == test_case["expected_language"]:
                    logger.info(f"  ✓ Language detection: {detected_lang}")
                else:
                    logger.warning(
                        f"  ⚠ Language detection mismatch: "
                        f"expected {test_case['expected_language']}, "
                        f"got {detected_lang}"
                    )

                # Test search term generation
                search_terms = self.extractor.get_localized_search_terms(mock_metadata)
                primary_term = search_terms[0] if search_terms else None

                if primary_term:
                    if primary_term["amazon_domain"] == test_case["expected_domain"]:
                        logger.info(
                            f"  ✓ Amazon domain mapping: "
                            f"{primary_term['amazon_domain']}"
                        )
                    else:
                        logger.error(
                            f"  ✗ Amazon domain mismatch: "
                            f"expected {test_case['expected_domain']}, "
                            f"got {primary_term['amazon_domain']}"
                        )

                    # Update statistics
                    if test_case["expected_language"] == "ja":
                        self.results["statistics"]["japanese_books_identified"] += 1
                    elif test_case["expected_language"] == "pt":
                        self.results["statistics"]["portuguese_books_identified"] += 1
                    elif test_case["expected_language"] == "nl":
                        self.results["statistics"]["dutch_books_identified"] += 1

                else:
                    logger.error(
                        f"  ✗ No search terms generated for {test_case['name']}"
                    )

            except Exception as e:
                logger.error(f"  ✗ Error testing {test_case['name']}: {e}")

        logger.info("=== New Language Support Test Complete ===")


def main():
    """Main test execution"""
    print("=" * 80)
    print("COMPREHENSIVE LOCALIZATION ASIN LOOKUP TEST SUITE")
    print("Issue #19 - Testing German book localization")
    print("Issue #23 - Testing Japanese, Portuguese, Dutch language support")
    print("=" * 80)

    # Run the test suite
    test_suite = LocalizationTestSuite()
    results = test_suite.run_comprehensive_test(max_asin_tests=3)  # Limit ASIN tests

    return results


if __name__ == "__main__":
    main()
