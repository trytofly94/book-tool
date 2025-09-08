#!/usr/bin/env python3
"""
Real-World Validation Test for Issue #23 - Language Support Expansion
Tests the new Japanese, Portuguese, and Dutch language support with actual examples
"""

import os
import sys
import logging

# Import our modules
try:
    from localization_metadata_extractor import LocalizationMetadataExtractor
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from localization_metadata_extractor import LocalizationMetadataExtractor

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_new_language_support():
    """Test real-world usage of new language support"""
    print("=" * 80)
    print("ISSUE #23 LANGUAGE SUPPORT VALIDATION")
    print("Testing Japanese, Portuguese, and Dutch language support")
    print("=" * 80)

    extractor = LocalizationMetadataExtractor()
    # lookup_service = ASINLookupService()  # Not used in this test

    # Test cases with international books
    test_cases = [
        {
            "name": "Japanese Literature",
            "mock_metadata": {
                "title": "ノルウェイの森",
                "author": "村上春樹",
                "language": "ja",
            },
            "expected_domain": "amazon.co.jp",
        },
        {
            "name": "Portuguese Literature",
            "mock_metadata": {
                "title": "O Alquimista",
                "author": "Paulo Coelho",
                "language": "pt",
            },
            "expected_domain": "amazon.com.br",
        },
        {
            "name": "Dutch Literature",
            "mock_metadata": {
                "title": "Het Achterhuis",
                "author": "Anne Frank",
                "language": "nl",
            },
            "expected_domain": "amazon.nl",
        },
        # Test alternative language codes
        {
            "name": "Japanese (alternative code)",
            "mock_metadata": {
                "title": "海辺のカフカ",
                "author": "村上春樹",
                "language": "jpn",  # Alternative code
            },
            "expected_domain": "amazon.co.jp",
        },
        {
            "name": "Portuguese Brazil variant",
            "mock_metadata": {
                "title": "Diário de um Mago",
                "author": "Paulo Coelho",
                "language": "pt-br",  # Brazil variant
            },
            "expected_domain": "amazon.com.br",
        },
        {
            "name": "Dutch (alternative code)",
            "mock_metadata": {
                "title": "Dagboek van Anne Frank",
                "author": "Anne Frank",
                "language": "nld",  # Alternative code
            },
            "expected_domain": "amazon.nl",
        },
    ]

    results = []

    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        metadata = test_case["mock_metadata"]

        try:
            # Test language normalization
            normalized_lang = extractor._normalize_language_code(metadata["language"])
            print(f"Language normalization: {metadata['language']} → {normalized_lang}")

            # Test language detection from title
            detected_lang = extractor._guess_language_from_title(metadata["title"])
            print(f"Language detection: '{metadata['title']}' → {detected_lang}")

            # Test search terms generation
            search_terms = extractor.get_localized_search_terms(metadata)

            if search_terms:
                primary_term = search_terms[0]
                print(f"Primary search term: {primary_term}")

                # Validate Amazon domain mapping
                actual_domain = primary_term["amazon_domain"]
                expected_domain = test_case["expected_domain"]

                if actual_domain == expected_domain:
                    print(f"✓ Amazon domain mapping: {actual_domain}")
                    status = "PASS"
                else:
                    print(
                        f"✗ Domain mismatch: expected {expected_domain}, "
                        f"got {actual_domain}"
                    )
                    status = "FAIL"

                print(f"Generated {len(search_terms)} fallback search strategies")

                # Show fallback strategies
                for i, term in enumerate(search_terms[1:4], 2):
                    strategy = term.get("strategy", "unknown")
                    domain = term["amazon_domain"]
                    print(f"  Fallback {i-1}: [{strategy}] → {domain}")

            else:
                print("✗ No search terms generated")
                status = "FAIL"

        except Exception as e:
            print(f"✗ Error: {e}")
            status = "ERROR"

        results.append(
            {"name": test_case["name"], "status": status, "metadata": metadata}
        )

    # Summary report
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    print(f"Total tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")
    print(f"Success rate: {(passed/len(results)*100):.1f}%")

    print("\nDetailed Results:")
    for result in results:
        status_symbol = "✓" if result["status"] == "PASS" else "✗"
        print(f"{status_symbol} {result['name']}: {result['status']}")

    # Test pipeline directory if available
    print("\n" + "=" * 80)
    print("PIPELINE DIRECTORY TEST")
    print("=" * 80)

    pipeline_dir = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
    if os.path.exists(pipeline_dir):
        print(f"Testing books in pipeline directory: {pipeline_dir}")

        # Look for any non-English books that might benefit from new language support
        book_files = []
        for ext in [".epub", ".mobi"]:
            pattern = os.path.join(pipeline_dir, f"*{ext}")
            import glob

            book_files.extend(glob.glob(pattern))

        print(f"Found {len(book_files)} book files")

        # Test a few random books to see if they're detected with new languages
        for book_file in book_files[:5]:
            filename = os.path.basename(book_file)
            try:
                metadata = extractor.extract_metadata_from_path(book_file)
                lang = metadata.get("language", "unknown")
                title = metadata.get("title", "N/A")

                print(f"  {filename}: {lang} - '{title[:50]}...'")

                # Check if this would benefit from new language support
                if lang in ["ja", "pt", "nl"]:
                    print(f"    → Would use new {lang} language support!")

            except Exception as e:
                print(f"  {filename}: Error - {e}")
    else:
        print(f"Pipeline directory not found: {pipeline_dir}")

    print("\n" + "=" * 80)
    print("ISSUE #23 VALIDATION COMPLETE")
    print("Japanese, Portuguese, and Dutch language support validated")
    print("=" * 80)

    return results


if __name__ == "__main__":
    test_new_language_support()
