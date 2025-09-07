#!/usr/bin/env python3
"""
Real-world manual testing script for GitHub issue #18 ASIN lookup fixes.

This script performs actual lookups against real APIs to validate that the 
title/author search functionality works correctly. 

Usage:
    python test_issue18_real_world.py [--verbose]

WARNING: This makes actual network requests and may be rate-limited.
Use sparingly and respectfully.
"""

import sys
import time
import tempfile
import argparse
from pathlib import Path
from unittest.mock import Mock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from calibre_books.core.asin_lookup import ASINLookupService


def create_test_service():
    """Create an ASIN lookup service for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_path = Path(temp_dir) / "real_world_test_cache.json"
        
        mock_config_manager = Mock()
        mock_config_manager.get_asin_config.return_value = {
            'cache_path': str(cache_path),
            'sources': ['amazon', 'goodreads', 'openlibrary'],
            'rate_limit': 3.0  # Be respectful to APIs
        }
        
        return ASINLookupService(mock_config_manager)


def test_issue18_examples(verbose=False):
    """Test the specific examples from GitHub issue #18."""
    print("Testing GitHub Issue #18 Examples")
    print("=" * 50)
    
    service = create_test_service()
    
    # Test cases from the original issue report
    test_cases = [
        ("The Way of Kings", "Brandon Sanderson"),
        ("Mistborn", "Brandon Sanderson"), 
        ("The Hobbit", "J.R.R. Tolkien"),
    ]
    
    results = []
    
    for i, (title, author) in enumerate(test_cases, 1):
        print(f"\nTest {i}/3: '{title}' by {author}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            result = service.lookup_by_title(title, author=author, verbose=verbose)
            lookup_time = time.time() - start_time
            
            if result.success:
                print(f"✓ SUCCESS: Found ASIN {result.asin}")
                print(f"  Source: {result.source}")
                print(f"  Lookup time: {lookup_time:.2f}s")
                print(f"  From cache: {result.from_cache}")
                
                if verbose and result.metadata:
                    print("  Detailed results:")
                    for source, details in result.metadata.items():
                        print(f"    {source}: {details}")
                
                results.append((title, author, True, result.asin, result.source))
            else:
                print(f"✗ FAILED: {result.error}")
                print(f"  Lookup time: {lookup_time:.2f}s")
                
                if verbose and result.metadata:
                    print("  Failure details:")
                    for source, details in result.metadata.items():
                        print(f"    {source}: {details}")
                
                results.append((title, author, False, None, None))
                
        except Exception as e:
            print(f"✗ ERROR: {e}")
            results.append((title, author, False, None, f"Exception: {e}"))
        
        # Be respectful to APIs - add delay between requests
        if i < len(test_cases):
            print("  Waiting 3 seconds before next request...")
            time.sleep(3)
    
    return results


def test_error_cases(verbose=False):
    """Test error handling with non-existent books."""
    print("\n\nTesting Error Handling")
    print("=" * 50)
    
    service = create_test_service()
    
    # Books that definitely don't exist
    error_cases = [
        ("Completely Nonexistent Book Title That Should Never Exist", "Fake Author Name"),
        ("", ""),  # Empty strings
        ("A", "B"),  # Very short strings
    ]
    
    results = []
    
    for i, (title, author) in enumerate(error_cases, 1):
        print(f"\nError Test {i}/{len(error_cases)}: '{title}' by '{author}'")
        print("-" * 40)
        
        try:
            start_time = time.time()
            result = service.lookup_by_title(title, author=author, verbose=verbose)
            lookup_time = time.time() - start_time
            
            if result.success:
                print(f"⚠ UNEXPECTED SUCCESS: Found ASIN {result.asin} (this may be incorrect)")
                results.append((title, author, "unexpected_success", result.asin))
            else:
                print(f"✓ EXPECTED FAILURE: {result.error[:100]}...")
                print(f"  Lookup time: {lookup_time:.2f}s")
                
                if verbose and result.metadata:
                    print("  Error details:")
                    for source, details in result.metadata.items():
                        print(f"    {source}: {details}")
                
                results.append((title, author, "expected_failure", result.error))
                
        except Exception as e:
            print(f"✗ UNEXPECTED ERROR: {e}")
            results.append((title, author, "unexpected_error", str(e)))
        
        # Be respectful to APIs
        if i < len(error_cases):
            time.sleep(2)
    
    return results


def test_asin_validation():
    """Test ASIN validation functionality."""
    print("\n\nTesting ASIN Validation")
    print("=" * 50)
    
    service = create_test_service()
    
    test_cases = [
        # Valid ASINs
        ("B00ZVA3XL6", True),
        ("B123456789", True),
        ("b00zva3xl6", True),  # Lowercase
        
        # Invalid ASINs
        ("A123456789", False),  # Non-B prefix
        ("9780765326355", False),  # ISBN
        ("", False),  # Empty
        ("B12345", False),  # Too short
        ("B123456789X", False),  # Too long
        ("1234567890", False),  # Number
    ]
    
    all_passed = True
    
    for asin, expected in test_cases:
        actual = service.validate_asin(asin)
        if actual == expected:
            print(f"✓ '{asin}' -> {actual} (expected {expected})")
        else:
            print(f"✗ '{asin}' -> {actual} (expected {expected})")
            all_passed = False
    
    return all_passed


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Real-world testing for ASIN lookup issue #18 fixes")
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--validation-only', action='store_true', help='Only run validation tests (no network calls)')
    args = parser.parse_args()
    
    print("ASIN Lookup Issue #18 Real-World Testing")
    print("========================================")
    print("This script tests the fixes for GitHub issue #18 where title/author")
    print("searches were returning 'No ASIN found from any source'")
    print()
    
    if args.validation_only:
        print("Running validation tests only (no network calls)")
        validation_passed = test_asin_validation()
        
        print("\n\nSUMMARY")
        print("=" * 50)
        if validation_passed:
            print("✓ All validation tests passed")
            return 0
        else:
            print("✗ Some validation tests failed")
            return 1
    
    print("WARNING: This will make actual network requests to book APIs.")
    print("Please be respectful of rate limits and API usage policies.")
    print()
    
    try:
        # Test ASIN validation first (no network calls)
        validation_passed = test_asin_validation()
        
        # Test the main issue examples
        issue_results = test_issue18_examples(verbose=args.verbose)
        
        # Test error handling
        error_results = test_error_cases(verbose=args.verbose)
        
        # Summary
        print("\n\nSUMMARY")
        print("=" * 50)
        
        print(f"Validation tests: {'PASSED' if validation_passed else 'FAILED'}")
        
        successful_lookups = sum(1 for _, _, success, _, _ in issue_results if success)
        print(f"Issue #18 examples: {successful_lookups}/{len(issue_results)} succeeded")
        
        expected_failures = sum(1 for _, _, result, _ in error_results if result == "expected_failure")
        print(f"Error handling: {expected_failures}/{len(error_results)} behaved correctly")
        
        print("\nDetailed Results:")
        print("Issue #18 Examples:")
        for title, author, success, asin, source in issue_results:
            status = "✓" if success else "✗"
            print(f"  {status} '{title}' by {author}: {asin or 'No ASIN'} ({source or 'No source'})")
        
        # Overall assessment
        if validation_passed and successful_lookups >= 2:  # At least 2/3 should work
            print("\n🎉 OVERALL: Issue #18 fixes appear to be working correctly!")
            print("   Title/author searches are now finding ASINs as expected.")
            return 0
        else:
            print("\n⚠ OVERALL: Issue #18 fixes may need more work.")
            print("   Some expected lookups are still failing.")
            return 1
            
    except KeyboardInterrupt:
        print("\n\nTesting interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\nUnexpected error during testing: {e}")
        return 1


if __name__ == "__main__":
    exit(main())