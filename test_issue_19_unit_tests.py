#!/usr/bin/env python3
"""
Unit Tests for Issue #19 - Localization ASIN Lookup
Comprehensive unit tests with mocking for all components
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch
import tempfile

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from localization_metadata_extractor import LocalizationMetadataExtractor
from enhanced_asin_lookup import ASINLookupService


class TestLocalizationMetadataExtractor(unittest.TestCase):
    """Unit tests for LocalizationMetadataExtractor"""

    def setUp(self):
        self.extractor = LocalizationMetadataExtractor()

    def test_language_mappings_initialization(self):
        """Test that language mappings are properly initialized"""
        self.assertIn("de", self.extractor.language_mappings)
        self.assertIn("fr", self.extractor.language_mappings)
        self.assertEqual(
            self.extractor.language_mappings["de"]["amazon_domain"], "amazon.de"
        )
        self.assertEqual(
            self.extractor.language_mappings["fr"]["amazon_domain"], "amazon.fr"
        )

    def test_title_patterns_initialization(self):
        """Test that title patterns are properly initialized"""
        self.assertIn("mistborn", self.extractor.title_patterns)
        self.assertIn("stormlight", self.extractor.title_patterns)

        mistborn = self.extractor.title_patterns["mistborn"]
        self.assertIn("english", mistborn)
        self.assertIn("german", mistborn)
        self.assertIn("Mistborn", mistborn["english"])
        self.assertIn("Kinder des Nebels", mistborn["german"])

    def test_normalize_language_code(self):
        """Test language code normalization"""
        # Test standard codes
        self.assertEqual(self.extractor._normalize_language_code("de"), "de")
        self.assertEqual(self.extractor._normalize_language_code("en"), "en")

        # Test alternative codes
        self.assertEqual(self.extractor._normalize_language_code("deu"), "de")
        self.assertEqual(self.extractor._normalize_language_code("ger"), "de")
        self.assertEqual(self.extractor._normalize_language_code("eng"), "en")

        # Test fallback
        self.assertEqual(self.extractor._normalize_language_code(""), "en")
        self.assertEqual(self.extractor._normalize_language_code("unknown"), "en")

    def test_guess_language_from_title(self):
        """Test language guessing from title patterns"""
        # Test German titles
        self.assertEqual(
            self.extractor._guess_language_from_title("Kinder des Nebels"), "de"
        )
        self.assertEqual(
            self.extractor._guess_language_from_title("Der Weg der Könige"), "de"
        )
        self.assertEqual(
            self.extractor._guess_language_from_title("Ruf der Sterne"), "de"
        )

        # Test French titles
        self.assertEqual(
            self.extractor._guess_language_from_title("Les enfants de la brume"), "fr"
        )

        # Test English fallback
        self.assertEqual(self.extractor._guess_language_from_title("Mistborn"), "en")
        self.assertEqual(
            self.extractor._guess_language_from_title("The Way of Kings"), "en"
        )
        self.assertEqual(self.extractor._guess_language_from_title(""), "en")

    def test_extract_from_filename(self):
        """Test metadata extraction from filename"""
        # Test basic pattern
        metadata = self.extractor.extract_from_filename(
            "/path/sanderson_mistborn1_kinder-des-nebels.epub"
        )
        self.assertEqual(metadata["author"], "Sanderson")
        self.assertEqual(metadata["series"], "Mistborn1")
        self.assertEqual(metadata["title"], "Kinder Des Nebels")
        self.assertEqual(metadata["language"], "de")

        # Test author-title pattern
        metadata = self.extractor.extract_from_filename(
            "/path/brandon-sanderson_elantris.epub"
        )
        self.assertEqual(metadata["author"], "Brandon Sanderson")
        self.assertEqual(metadata["title"], "Elantris")

    def test_clean_title_for_search(self):
        """Test title cleaning for search optimization"""
        # Test series number removal
        cleaned = self.extractor._clean_title_for_search("Series Book 1 - Title")
        self.assertEqual(cleaned, "Series Book Title")  # Numbers and dashes are removed

        # Test parenthetical removal
        cleaned = self.extractor._clean_title_for_search("Title (German Edition)")
        self.assertEqual(cleaned, "Title")

        # Test bracket removal
        cleaned = self.extractor._clean_title_for_search("Title [Book Series]")
        self.assertEqual(cleaned, "Title")

        # Test whitespace cleanup
        cleaned = self.extractor._clean_title_for_search("Title   with   spaces")
        self.assertEqual(cleaned, "Title with spaces")

    def test_find_english_equivalent(self):
        """Test finding English equivalents of localized titles"""
        # Test known German -> English mapping
        english = self.extractor._find_english_equivalent(
            "Kinder des Nebels", "Brandon Sanderson"
        )
        self.assertEqual(english, "Mistborn")

        # Test known German -> English for Stormlight
        english = self.extractor._find_english_equivalent(
            "Der Weg der Könige", "Brandon Sanderson"
        )
        self.assertEqual(english, "The Way of Kings")

        # Test unknown title
        english = self.extractor._find_english_equivalent(
            "Unknown German Title", "Some Author"
        )
        self.assertIsNone(english)

    def test_get_localized_search_terms(self):
        """Test generation of localized search terms"""
        metadata = {
            "title": "Kinder des Nebels",
            "author": "Brandon Sanderson",
            "language": "de",
            "series": "Mistborn",
        }

        search_terms = self.extractor.get_localized_search_terms(metadata)

        # Should have multiple search strategies
        self.assertGreater(len(search_terms), 3)

        # First should be localized primary
        first_term = search_terms[0]
        self.assertEqual(first_term["strategy"], "localized_primary")
        self.assertEqual(first_term["amazon_domain"], "amazon.de")
        self.assertEqual(first_term["language"], "de")

        # Should have English equivalent
        english_terms = [
            t for t in search_terms if t["strategy"] == "english_equivalent"
        ]
        self.assertEqual(len(english_terms), 1)
        self.assertEqual(english_terms[0]["title"], "Mistborn")

    def test_get_localized_search_terms_empty_metadata(self):
        """Test search terms generation with empty metadata"""
        empty_metadata = {}
        search_terms = self.extractor.get_localized_search_terms(empty_metadata)
        self.assertEqual(len(search_terms), 0)

    def test_get_localized_search_terms_fallbacks(self):
        """Test search terms fallback mechanisms"""
        metadata = {
            "title": "",  # Empty title to trigger fallbacks
            "author": "Brandon Sanderson",
            "language": "de",
            "series": "Mistborn",
        }

        search_terms = self.extractor.get_localized_search_terms(metadata)

        # Should use series as title fallback
        self.assertGreater(len(search_terms), 0)
        # First term should use series name
        self.assertEqual(search_terms[0]["title"], "Mistborn")

    def test_is_metadata_valid(self):
        """Test metadata validation"""
        # Valid metadata
        valid = {"title": "Valid Title", "author": "Valid Author"}
        self.assertTrue(self.extractor._is_metadata_valid(valid))

        # Valid with only title
        valid_title_only = {"title": "Valid Title", "author": ""}
        self.assertTrue(self.extractor._is_metadata_valid(valid_title_only))

        # Valid with only author
        valid_author_only = {"title": "", "author": "Valid Author"}
        self.assertTrue(self.extractor._is_metadata_valid(valid_author_only))

        # Invalid - both empty
        invalid = {"title": "", "author": ""}
        self.assertFalse(self.extractor._is_metadata_valid(invalid))

        # Invalid - too short
        invalid_short = {"title": "A", "author": "B"}
        self.assertFalse(self.extractor._is_metadata_valid(invalid_short))

        # Invalid - None
        self.assertFalse(self.extractor._is_metadata_valid(None))
        self.assertFalse(self.extractor._is_metadata_valid({}))

    def test_is_likely_corrupted(self):
        """Test corruption detection"""
        # Test with common corruption error messages
        zip_error = Exception("File is not a zip file")
        self.assertTrue(self.extractor._is_likely_corrupted("/fake/path", zip_error))

        bad_zip_error = Exception("Bad zipfile")
        self.assertTrue(
            self.extractor._is_likely_corrupted("/fake/path", bad_zip_error)
        )

        # Test with non-corruption error
        other_error = Exception("Permission denied")
        self.assertFalse(self.extractor._is_likely_corrupted("/fake/path", other_error))

    def test_merge_metadata(self):
        """Test metadata merging"""
        primary = {"title": "Primary Title", "author": "", "language": "de"}
        fallback = {
            "title": "Fallback Title",
            "author": "Fallback Author",
            "language": "en",
        }

        merged = self.extractor._merge_metadata(primary, fallback)

        # Should use primary when available
        self.assertEqual(merged["title"], "Primary Title")
        self.assertEqual(merged["language"], "de")

        # Should use fallback when primary is empty
        self.assertEqual(merged["author"], "Fallback Author")


class TestASINLookupService(unittest.TestCase):
    """Unit tests for ASINLookupService"""

    def setUp(self):
        # Create temporary cache file
        self.temp_cache = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        )
        self.temp_cache.write("{}")
        self.temp_cache.close()

        self.lookup_service = ASINLookupService(
            cache_file=self.temp_cache.name, rate_limit=0.1
        )

    def tearDown(self):
        # Clean up temporary cache file
        if os.path.exists(self.temp_cache.name):
            os.unlink(self.temp_cache.name)

    def test_initialization(self):
        """Test service initialization"""
        self.assertIsNotNone(self.lookup_service.cache)
        self.assertIsInstance(self.lookup_service.user_agents, list)
        self.assertGreater(len(self.lookup_service.user_agents), 0)

    def test_validate_asin(self):
        """Test ASIN validation"""
        # Valid ASINs
        self.assertTrue(self.lookup_service.validate_asin("B001234567"))
        self.assertTrue(self.lookup_service.validate_asin("B123456789"))
        self.assertTrue(self.lookup_service.validate_asin("BABCDEF123"))

        # Invalid ASINs
        self.assertFalse(
            self.lookup_service.validate_asin("A001234567")
        )  # Doesn't start with B
        self.assertFalse(self.lookup_service.validate_asin("B12345678"))  # Too short
        self.assertFalse(self.lookup_service.validate_asin("B1234567890"))  # Too long
        self.assertFalse(self.lookup_service.validate_asin(""))  # Empty
        self.assertFalse(self.lookup_service.validate_asin(None))  # None

    def test_cache_operations(self):
        """Test cache loading and saving"""
        # Add item to cache
        self.lookup_service.cache["test_key"] = "B123456789"
        self.lookup_service.save_cache()

        # Create new service with same cache file
        new_service = ASINLookupService(cache_file=self.temp_cache.name)
        self.assertEqual(new_service.cache["test_key"], "B123456789")

    @patch("requests.get")
    def test_lookup_by_isbn_direct(self, mock_get):
        """Test direct ISBN to ASIN lookup"""
        # Mock successful response with ASIN in URL
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://www.amazon.com/dp/B123456789/ref=sr_1_1"
        mock_get.return_value = mock_response

        asin = self.lookup_service.lookup_by_isbn_direct("1234567890")
        self.assertEqual(asin, "B123456789")

        # Test with invalid response
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        asin = self.lookup_service.lookup_by_isbn_direct("1234567890")
        self.assertIsNone(asin)

    @patch("requests.get")
    def test_lookup_via_amazon_search_localized(self, mock_get):
        """Test localized Amazon search"""
        # Mock HTML response with ASIN
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"""
        <div data-asin="B123456789">
            <h3>Test Book</h3>
        </div>
        """
        mock_get.return_value = mock_response

        # Test German Amazon search
        asin = self.lookup_service.lookup_via_amazon_search_localized(
            "Kinder des Nebels", "Brandon Sanderson", "amazon.de"
        )
        self.assertEqual(asin, "B123456789")

        # Verify correct URL was called
        args, kwargs = mock_get.call_args
        self.assertIn("amazon.de", args[0])
        self.assertIn("Kinder+des+Nebels+Brandon+Sanderson", args[0])

    @patch("requests.get")
    def test_lookup_via_google_books(self, mock_get):
        """Test Google Books API lookup"""
        # Mock Google Books API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "volumeInfo": {
                        "industryIdentifiers": [
                            {"type": "ISBN_13", "identifier": "9781234567890"},
                            {"type": "OTHER", "identifier": "B123456789"},
                        ]
                    }
                }
            ]
        }
        mock_get.return_value = mock_response

        asin = self.lookup_service.lookup_via_google_books(
            "1234567890", "Test Title", "Test Author"
        )
        self.assertEqual(asin, "B123456789")

    @patch.object(LocalizationMetadataExtractor, "extract_metadata_from_path")
    @patch.object(LocalizationMetadataExtractor, "get_localized_search_terms")
    def test_lookup_multiple_sources_with_localization(
        self, mock_search_terms, mock_extract
    ):
        """Test multi-source lookup with localization"""
        # Mock metadata extraction
        mock_extract.return_value = {
            "title": "Kinder des Nebels",
            "author": "Brandon Sanderson",
            "language": "de",
        }

        # Mock search terms generation
        mock_search_terms.return_value = [
            {
                "title": "Kinder des Nebels",
                "author": "Brandon Sanderson",
                "language": "de",
                "amazon_domain": "amazon.de",
                "priority": 1,
                "strategy": "localized_primary",
            }
        ]

        # Mock successful ASIN lookup
        with patch.object(
            self.lookup_service,
            "lookup_with_localized_terms",
            return_value="B123456789",
        ):
            asin = self.lookup_service.lookup_multiple_sources(
                file_path="/fake/path.epub"
            )
            self.assertEqual(asin, "B123456789")

    def test_lookup_multiple_sources_fallback(self):
        """Test fallback to standard lookup when localization not available"""
        # Test without localization extractor
        service_no_localization = ASINLookupService(cache_file=self.temp_cache.name)
        service_no_localization.localization_extractor = None

        with patch.object(
            service_no_localization,
            "lookup_standard_sources",
            return_value="B987654321",
        ):
            asin = service_no_localization.lookup_multiple_sources(
                title="Test Title", author="Test Author"
            )
            self.assertEqual(asin, "B987654321")


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete localization system"""

    def setUp(self):
        self.extractor = LocalizationMetadataExtractor()
        self.temp_cache = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        )
        self.temp_cache.write("{}")
        self.temp_cache.close()
        self.lookup_service = ASINLookupService(
            cache_file=self.temp_cache.name, rate_limit=0.1
        )

    def tearDown(self):
        if os.path.exists(self.temp_cache.name):
            os.unlink(self.temp_cache.name)

    def test_end_to_end_localization_flow(self):
        """Test complete flow from metadata extraction to ASIN lookup"""
        # Test data that would come from a German book
        test_metadata = {
            "title": "Kinder des Nebels",
            "author": "Brandon Sanderson",
            "language": "de",
            "series": "Mistborn",
        }

        # Test search terms generation
        search_terms = self.extractor.get_localized_search_terms(test_metadata)

        # Verify we have the expected search strategies
        self.assertGreater(len(search_terms), 3)

        # Verify localized primary search
        localized_primary = next(
            t for t in search_terms if t["strategy"] == "localized_primary"
        )
        self.assertEqual(localized_primary["amazon_domain"], "amazon.de")
        self.assertEqual(localized_primary["language"], "de")

        # Verify English equivalent search
        english_equivalent = next(
            (t for t in search_terms if t["strategy"] == "english_equivalent"), None
        )
        if english_equivalent:  # Should exist for known series
            self.assertEqual(english_equivalent["amazon_domain"], "amazon.com")
            self.assertEqual(english_equivalent["title"], "Mistborn")

    def test_edge_case_handling(self):
        """Test handling of edge cases in the complete system"""
        # Test with empty metadata
        empty_metadata = {}
        search_terms = self.extractor.get_localized_search_terms(empty_metadata)
        self.assertEqual(len(search_terms), 0)

        # Test with minimal metadata
        minimal_metadata = {"title": "Unknown Title", "author": "Unknown Author"}
        search_terms = self.extractor.get_localized_search_terms(minimal_metadata)
        self.assertGreater(len(search_terms), 0)  # Should have fallback strategies

        # Test corruption detection
        fake_error = Exception("File is not a zip file")
        is_corrupted = self.extractor._is_likely_corrupted(
            "/fake/path.epub", fake_error
        )
        self.assertTrue(is_corrupted)


def run_unit_tests():
    """Run all unit tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLocalizationMetadataExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestASINLookupService))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    print("=" * 80)
    print("UNIT TESTS FOR ISSUE #19 - LOCALIZATION ASIN LOOKUP")
    print("=" * 80)

    success = run_unit_tests()

    if success:
        print("\n✓ All unit tests passed!")
        print("Issue #19 localization features are working correctly.")
    else:
        print("\n✗ Some unit tests failed!")
        print("Please review the test results above.")

    sys.exit(0 if success else 1)
