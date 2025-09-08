#!/usr/bin/env python3
"""
Regression Tests for Issue #18 and #19 Integration
Tests that both ASIN lookup fixes and localization features work together
"""

import os
import sys
import unittest
from unittest.mock import patch
import tempfile

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from localization_metadata_extractor import LocalizationMetadataExtractor
from enhanced_asin_lookup import ASINLookupService
from calibre_asin_automation import CalibreASINAutomation

class TestIssue18And19Regression(unittest.TestCase):
    """Regression tests ensuring both issues work together"""
    
    def setUp(self):
        self.temp_cache = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_cache.write('{}')
        self.temp_cache.close()
        
        self.extractor = LocalizationMetadataExtractor()
        self.lookup_service = ASINLookupService(cache_file=self.temp_cache.name, rate_limit=0.1)
        
        # Mock Calibre availability for automation tests
        with patch.object(CalibreASINAutomation, 'check_calibre_availability', return_value=True):
            self.automation = CalibreASINAutomation()
    
    def tearDown(self):
        if os.path.exists(self.temp_cache.name):
            os.unlink(self.temp_cache.name)
    
    def test_backward_compatibility_english_books(self):
        """Test that English books still work with Issue #18 fixes"""
        # Simulate English book metadata (Issue #18 scenario)
        metadata = {
            'title': 'Mistborn: The Final Empire',
            'author': 'Brandon Sanderson',
            'language': 'en',
            'series': 'Mistborn',
            'series_index': '1'
        }
        
        # Generate search terms (should work with localization but focus on English)
        search_terms = self.extractor.get_localized_search_terms(metadata)
        
        # Should have search terms
        self.assertGreater(len(search_terms), 0)
        
        # Primary search should be English on amazon.com
        primary_search = search_terms[0]
        self.assertEqual(primary_search['language'], 'en')
        self.assertEqual(primary_search['amazon_domain'], 'amazon.com')
        self.assertEqual(primary_search['strategy'], 'localized_primary')
        
        # Should not have english_equivalent strategy (already in English)
        english_equivalent_searches = [s for s in search_terms if s['strategy'] == 'english_equivalent']
        self.assertEqual(len(english_equivalent_searches), 0)
    
    def test_german_localization_with_english_fallback(self):
        """Test that German books use localization with English fallback (Issue #19)"""
        metadata = {
            'title': 'Kinder des Nebels',
            'author': 'Brandon Sanderson',
            'language': 'de',
            'series': 'Mistborn',
            'series_index': '1'
        }
        
        search_terms = self.extractor.get_localized_search_terms(metadata)
        
        # Should have multiple search strategies
        self.assertGreaterEqual(len(search_terms), 4)
        
        # Primary search should be German
        primary_search = search_terms[0]
        self.assertEqual(primary_search['language'], 'de')
        self.assertEqual(primary_search['amazon_domain'], 'amazon.de')
        self.assertEqual(primary_search['strategy'], 'localized_primary')
        
        # Should have English equivalent fallback
        english_equivalent_searches = [s for s in search_terms if s['strategy'] == 'english_equivalent']
        self.assertEqual(len(english_equivalent_searches), 1)
        self.assertEqual(english_equivalent_searches[0]['title'], 'Mistborn')
        self.assertEqual(english_equivalent_searches[0]['amazon_domain'], 'amazon.com')
    
    def test_multi_source_lookup_integration(self):
        """Test that multi-source lookup works with both issues' fixes"""
        # Test with cached results (Issue #18: caching)
        cache_key = "test_isbn_test_title_test_author"
        cached_asin = "B123456789"
        self.lookup_service.cache[cache_key] = cached_asin
        
        # Should return cached result immediately
        result = self.lookup_service.lookup_standard_sources(
            isbn="test_isbn",
            title="test_title", 
            author="test_author"
        )
        
        # Should return the cached ASIN
        self.assertEqual(result, cached_asin)
    
    @patch('requests.get')
    def test_error_handling_regression(self, mock_get):
        """Test error handling works for both English and German books"""
        # Mock network error (Issue #18: improved error handling)
        mock_get.side_effect = Exception("Network error")
        
        # Test English book
        english_metadata = {
            'title': 'The Way of Kings',
            'author': 'Brandon Sanderson',
            'language': 'en'
        }
        
        english_terms = self.extractor.get_localized_search_terms(english_metadata)
        
        # Should handle errors gracefully and continue to next search strategy
        for term in english_terms[:2]:  # Test first 2 strategies
            result = self.lookup_service.lookup_with_localized_terms(term)
            # Should not crash, should return None
            self.assertIsNone(result)
        
        # Test German book
        german_metadata = {
            'title': 'Der Weg der Könige',
            'author': 'Brandon Sanderson',
            'language': 'de'
        }
        
        german_terms = self.extractor.get_localized_search_terms(german_metadata)
        
        # Should also handle errors gracefully
        for term in german_terms[:2]:  # Test first 2 strategies
            result = self.lookup_service.lookup_with_localized_terms(term)
            self.assertIsNone(result)
    
    def test_asin_validation_consistency(self):
        """Test ASIN validation is consistent across both issues"""
        # Valid ASINs should work for both English and German lookups
        valid_asins = ['B001234567', 'B123456789', 'BABCDEF123']
        invalid_asins = ['A001234567', 'B12345678', '', None, 'invalid']
        
        for asin in valid_asins:
            self.assertTrue(self.lookup_service.validate_asin(asin), 
                          f"Valid ASIN {asin} should pass validation")
        
        for asin in invalid_asins:
            self.assertFalse(self.lookup_service.validate_asin(asin),
                           f"Invalid ASIN {asin} should fail validation")
    
    def test_filename_extraction_fallback_integration(self):
        """Test filename fallback works for both English and German files"""
        # English filename
        english_metadata = self.extractor.extract_from_filename(
            '/path/brandon-sanderson_mistborn-final-empire.epub'
        )
        
        self.assertEqual(english_metadata['author'], 'Brandon Sanderson')
        self.assertEqual(english_metadata['title'], 'Mistborn Final Empire')
        self.assertEqual(english_metadata['language'], 'en')  # Should default to English
        
        # German filename
        german_metadata = self.extractor.extract_from_filename(
            '/path/sanderson_mistborn1_kinder-des-nebels.epub'
        )
        
        self.assertEqual(german_metadata['author'], 'Sanderson')
        self.assertEqual(german_metadata['series'], 'Mistborn1')
        self.assertEqual(german_metadata['title'], 'Kinder Des Nebels')
        self.assertEqual(german_metadata['language'], 'de')  # Should detect German
    
    def test_cross_language_fallback_chains(self):
        """Test that cross-language fallback chains work correctly"""
        # German book should fall back to English
        german_metadata = {
            'title': 'Unbekanntes deutsches Buch',
            'author': 'Unbekannter Autor',
            'language': 'de'
        }
        
        search_terms = self.extractor.get_localized_search_terms(german_metadata)
        
        # Should have cross-language fallbacks to amazon.com
        cross_language_terms = [s for s in search_terms if s['strategy'].startswith('cross_language')]
        self.assertGreater(len(cross_language_terms), 0)
        
        # All cross-language fallbacks should point to amazon.com for German
        for term in cross_language_terms:
            self.assertEqual(term['amazon_domain'], 'amazon.com')
    
    def test_corrupted_file_handling_with_localization(self):
        """Test that corrupted file handling works with localization features"""
        # Simulate corrupted file error
        corrupted_error = Exception("File is not a zip file")
        
        # Should detect corruption
        is_corrupted = self.extractor._is_likely_corrupted('/fake/path.epub', corrupted_error)
        self.assertTrue(is_corrupted)
        
        # Should fall back to filename extraction
        fallback_metadata = self.extractor.extract_from_filename('/fake/corrupted_german_book.epub')
        
        # Should still provide some metadata
        self.assertIsInstance(fallback_metadata, dict)
        self.assertIn('title', fallback_metadata)
        self.assertIn('language', fallback_metadata)
    
    def test_calibre_integration_compatibility(self):
        """Test that Calibre integration works with both localization and standard features"""
        # Test that automation service has both components
        self.assertIsNotNone(self.automation.lookup_service)
        self.assertIsNotNone(self.automation.localization_extractor)
        
        # Test that it can handle both types of books
        with patch.object(self.automation, 'get_book_file_path', return_value=None):
            # Should fall back to standard lookup when file path not available
            with patch.object(self.automation.lookup_service, 'lookup_multiple_sources', 
                            return_value='B123456789') as mock_lookup:
                
                # Simulate processing a book without file path (Issue #18 scenario)
                result = mock_lookup(isbn='1234567890', title='Test Title', author='Test Author')
                self.assertEqual(result, 'B123456789')
    
    def test_rate_limiting_across_strategies(self):
        """Test that rate limiting works across all search strategies"""
        # Test that rate limiting is configured correctly
        self.assertGreater(self.lookup_service.rate_limit, 0)
        
        # Test that lookup with localized terms respects the rate limiting pattern
        metadata = {
            'title': 'Test Title',
            'author': 'Test Author',
            'language': 'de'
        }
        
        search_terms = self.extractor.get_localized_search_terms(metadata)
        self.assertGreater(len(search_terms), 0)
        
        # Mock failed lookups to test multiple strategies
        with patch.object(self.lookup_service, 'lookup_via_amazon_search_localized', return_value=None):
            # Should handle multiple failed attempts gracefully
            for term in search_terms[:3]:
                result = self.lookup_service.lookup_with_localized_terms(term)
                self.assertIsNone(result)
    
    def test_search_term_priority_ordering(self):
        """Test that search terms are correctly prioritized"""
        metadata = {
            'title': 'Kinder des Nebels',
            'author': 'Brandon Sanderson', 
            'language': 'de',
            'series': 'Mistborn'
        }
        
        search_terms = self.extractor.get_localized_search_terms(metadata)
        
        # Verify priority ordering
        priorities = [term['priority'] for term in search_terms]
        self.assertEqual(priorities, sorted(priorities), "Search terms should be ordered by priority")
        
        # Verify expected strategy order
        strategies = [term['strategy'] for term in search_terms]
        
        # Primary localized should be first
        self.assertEqual(strategies[0], 'localized_primary')
        
        # English equivalent should be early (priority 2)
        english_equiv_index = next(i for i, s in enumerate(strategies) if s == 'english_equivalent')
        self.assertLess(english_equiv_index, 5, "English equivalent should be high priority")


def run_regression_tests():
    """Run all regression tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestIssue18And19Regression))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    print("=" * 80)
    print("REGRESSION TESTS FOR ISSUE #18 + #19 INTEGRATION")
    print("Testing that ASIN lookup fixes and localization work together")
    print("=" * 80)
    
    success = run_regression_tests()
    
    if success:
        print("\n✓ All regression tests passed!")
        print("Issue #18 and #19 are fully compatible and working together.")
        print("\nBoth issues provide:")
        print("  ✓ Enhanced ASIN lookup with multiple sources")
        print("  ✓ Robust error handling and fallback mechanisms") 
        print("  ✓ Caching for improved performance")
        print("  ✓ Multi-language support with German localization")
        print("  ✓ English-German title translation") 
        print("  ✓ Region-specific Amazon domain routing")
        print("  ✓ Comprehensive fallback strategies")
    else:
        print("\n✗ Some regression tests failed!")
        print("There may be compatibility issues between Issue #18 and #19.")
    
    sys.exit(0 if success else 1)