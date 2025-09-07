#!/usr/bin/env python3
"""
Comprehensive Review Testing Script for Issue #18/#19
Tests ASIN lookup functionality with real Brandon Sanderson books
"""

import os
import sys
import json
import time
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.getcwd())

try:
    from enhanced_asin_lookup import ASINLookupService
    from localization_metadata_extractor import LocalizationMetadataExtractor
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

def test_comprehensive_asin_lookup():
    """Test ASIN lookup with all available Brandon Sanderson books"""
    
    test_dir = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
    if not os.path.exists(test_dir):
        print(f"Test directory not found: {test_dir}")
        return
    
    # Initialize services
    asin_service = ASINLookupService()
    metadata_extractor = LocalizationMetadataExtractor()
    
    print("=" * 80)
    print("COMPREHENSIVE REVIEW TEST FOR ISSUE #18/#19")
    print("Testing ASIN Lookup with Brandon Sanderson Books")
    print("=" * 80)
    
    # Get all book files
    book_files = [f for f in os.listdir(test_dir) if f.endswith(('.epub', '.mobi'))]
    book_files.sort()
    
    print(f"\nFound {len(book_files)} book files to test:")
    for i, book in enumerate(book_files, 1):
        print(f"  {i:2d}. {book}")
    
    results = {
        'total_books': len(book_files),
        'metadata_extracted': 0,
        'german_books_identified': 0,
        'asin_lookups_attempted': 0,
        'asin_lookups_successful': 0,
        'detailed_results': []
    }
    
    # Test metadata extraction for all books
    print(f"\n{'='*80}")
    print("PHASE 1: METADATA EXTRACTION TEST")
    print(f"{'='*80}")
    
    for i, book_file in enumerate(book_files, 1):
        book_path = os.path.join(test_dir, book_file)
        print(f"\n[{i:2d}/{len(book_files)}] Testing: {book_file}")
        
        try:
            # Extract metadata
            metadata = metadata_extractor.extract_metadata_from_path(book_path)
            
            if metadata and metadata.get('title'):
                results['metadata_extracted'] += 1
                
                result = {
                    'file': book_file,
                    'title': metadata.get('title', 'Unknown'),
                    'language': metadata.get('language', 'Unknown'),
                    'author': metadata.get('author', 'Unknown'),
                    'series': metadata.get('series', ''),
                    'metadata_extracted': True,
                    'is_german': metadata.get('language') == 'de',
                    'asin_lookup_attempted': False,
                    'asin_found': None
                }
                
                if metadata.get('language') == 'de':
                    results['german_books_identified'] += 1
                    print(f"  ✓ German book identified: {metadata['title']}")
                else:
                    print(f"  ✓ Metadata: {metadata['title']} ({metadata.get('language', 'unknown')})")
                    
                results['detailed_results'].append(result)
            else:
                print(f"  ✗ Failed to extract metadata")
                results['detailed_results'].append({
                    'file': book_file,
                    'metadata_extracted': False,
                    'error': 'No metadata extracted'
                })
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results['detailed_results'].append({
                'file': book_file,
                'metadata_extracted': False,
                'error': str(e)
            })
    
    # Test ASIN lookup for a sample of German books
    print(f"\n{'='*80}")
    print("PHASE 2: ASIN LOOKUP TEST")
    print(f"{'='*80}")
    
    german_books = [r for r in results['detailed_results'] if r.get('is_german', False)]
    test_books = german_books[:3]  # Test first 3 German books
    
    if not test_books:
        print("No German books found for ASIN testing")
    else:
        print(f"Testing ASIN lookup for {len(test_books)} German books:")
        
        for i, book_result in enumerate(test_books, 1):
            book_path = os.path.join(test_dir, book_result['file'])
            print(f"\n[{i}/{len(test_books)}] ASIN Lookup: {book_result['file']}")
            print(f"  Title: {book_result['title']}")
            
            try:
                results['asin_lookups_attempted'] += 1
                book_result['asin_lookup_attempted'] = True
                
                # Attempt ASIN lookup using file path
                asin = asin_service.lookup_multiple_sources(file_path=book_path)
                
                if asin and asin.startswith('B'):
                    results['asin_lookups_successful'] += 1
                    book_result['asin_found'] = asin
                    print(f"  ✓ ASIN found: {asin}")
                else:
                    book_result['asin_found'] = None
                    print(f"  ✗ No valid ASIN found")
                    
                # Add small delay between requests
                time.sleep(1)
                
            except Exception as e:
                book_result['asin_found'] = None
                print(f"  ✗ ASIN lookup error: {e}")
    
    # Print final results
    print(f"\n{'='*80}")
    print("FINAL REVIEW RESULTS")
    print(f"{'='*80}")
    
    print(f"\n📊 SUMMARY STATISTICS:")
    print(f"  Total books processed: {results['total_books']}")
    print(f"  Metadata successfully extracted: {results['metadata_extracted']}")
    print(f"  German books identified: {results['german_books_identified']}")
    print(f"  ASIN lookups attempted: {results['asin_lookups_attempted']}")
    print(f"  ASIN lookups successful: {results['asin_lookups_successful']}")
    
    success_rate_metadata = (results['metadata_extracted'] / results['total_books']) * 100
    success_rate_asin = (results['asin_lookups_successful'] / max(results['asin_lookups_attempted'], 1)) * 100
    
    print(f"\n📈 SUCCESS RATES:")
    print(f"  Metadata extraction: {success_rate_metadata:.1f}%")
    print(f"  ASIN lookup: {success_rate_asin:.1f}%")
    
    # Show German books identified
    print(f"\n🇩🇪 GERMAN BOOKS IDENTIFIED:")
    german_count = 0
    for result in results['detailed_results']:
        if result.get('is_german', False):
            german_count += 1
            asin_status = f"ASIN: {result.get('asin_found', 'Not tested')}"
            print(f"  {german_count:2d}. {result['title']} - {asin_status}")
    
    # Check cache status
    try:
        with open('/tmp/asin_cache.json', 'r') as f:
            cache = json.load(f)
        print(f"\n💾 CACHE STATUS:")
        print(f"  Cached ASINs: {len(cache)}")
        for key, asin in cache.items():
            print(f"    {asin}: {key}")
    except:
        print(f"\n💾 CACHE STATUS: No cache file found")
    
    return results

if __name__ == "__main__":
    test_comprehensive_asin_lookup()