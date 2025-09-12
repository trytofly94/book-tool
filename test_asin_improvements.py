#!/usr/bin/env python3
"""
Test script to validate ASIN lookup improvements for Issue #55.

This script tests various challenging book title/author combinations
to measure the success rate improvements from the enhanced search features.
"""

import subprocess
import time

# Test cases - challenging variations to test the enhanced search
test_cases = [
    # Original cases from Issue #55
    {
        "title": "Elantris",
        "author": "Brandon Sanderson",
        "description": "Original Elantris test",
    },
    {
        "title": "Mistborn",
        "author": "Brandon Sanderson",
        "description": "Original Mistborn test",
    },
    {
        "title": "The Way of Kings",
        "author": "Brandon Sanderson",
        "description": "Original Way of Kings test",
    },
    # Enhanced cases - partial titles
    {
        "title": "Final Empire",
        "author": "Sanderson",
        "description": "Partial Mistborn title + short author",
    },
    {
        "title": "Way of Kings",
        "author": "B. Sanderson",
        "description": "Missing 'The' + abbreviated author",
    },
    # Series variations
    {
        "title": "Mistborn: The Final Empire",
        "author": "Brandon Sanderson",
        "description": "Full series title",
    },
    {
        "title": "The Final Empire",
        "author": "Brandon Sanderson",
        "description": "Subtitle only",
    },
    {
        "title": "Mistborn 1",
        "author": "Brandon Sanderson",
        "description": "Series with number",
    },
    # Misspellings and variations
    {
        "title": "Elantriss",
        "author": "Sanderson",
        "description": "Misspelled title + short author",
    },
    {
        "title": "Stormlight",
        "author": "Brandon Sanderson",
        "description": "Series name only",
    },
    # German titles from the test files
    {
        "title": "Kinder des Nebels",
        "author": "Brandon Sanderson",
        "description": "German Mistborn title",
    },
    {
        "title": "Weg der Könige",
        "author": "Brandon Sanderson",
        "description": "German Way of Kings title",
    },
    # Additional challenging cases
    {
        "title": "Warbreaker",
        "author": "Sanderson",
        "description": "Standalone book + short author",
    },
    {
        "title": "Skyward",
        "author": "B. Sanderson",
        "description": "Simple title + abbreviated author",
    },
    {
        "title": "Emperor's Soul",
        "author": "Brandon Sanderson",
        "description": "Apostrophe in title",
    },
]


def run_asin_lookup(title, author, use_fuzzy=True):
    """Run ASIN lookup and return success status and timing."""
    cmd = [
        "python3",
        "-m",
        "src.calibre_books.cli.main",
        "asin",
        "lookup",
        "--book",
        title,
        "--author",
        author,
    ]

    if use_fuzzy:
        cmd.extend(["--fuzzy", "--verbose"])
    else:
        cmd.extend(["--no-fuzzy", "--verbose"])

    start_time = time.time()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        elapsed = time.time() - start_time

        # Check if ASIN was found
        success = "ASIN found:" in result.stdout
        asin = None

        if success:
            # Extract ASIN from output
            for line in result.stdout.split("\n"):
                if "ASIN found:" in line:
                    asin = line.split("ASIN found:")[-1].strip()
                    break

        return {
            "success": success,
            "asin": asin,
            "elapsed": elapsed,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "asin": None,
            "elapsed": 30.0,
            "stdout": "",
            "stderr": "Timeout after 30 seconds",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "asin": None,
            "elapsed": time.time() - start_time,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
        }


def main():
    """Run comprehensive ASIN lookup tests."""
    print("🔍 ASIN Lookup Enhancement Testing (Issue #55)")
    print("=" * 60)

    # Clear cache first
    print("🧹 Clearing ASIN cache...")
    subprocess.run(
        ["python3", "-m", "src.calibre_books.cli.main", "asin", "cache", "--clear"],
        capture_output=True,
    )

    results_enhanced = []
    results_basic = []

    print(f"📚 Testing {len(test_cases)} challenging book title/author combinations...")
    print()

    for i, test_case in enumerate(test_cases, 1):
        title = test_case["title"]
        author = test_case["author"]
        description = test_case["description"]

        print(f"Test {i:2d}: {description}")
        print(f"         Title: '{title}' | Author: '{author}'")

        # Test with enhanced features
        print("         🔍 Enhanced search...", end=" ", flush=True)
        result_enhanced = run_asin_lookup(title, author, use_fuzzy=True)
        results_enhanced.append({**test_case, **result_enhanced})

        if result_enhanced["success"]:
            print(
                f"✅ Found {result_enhanced['asin']} ({result_enhanced['elapsed']:.1f}s)"
            )
        else:
            print(f"❌ Failed ({result_enhanced['elapsed']:.1f}s)")

        # Test with basic features only
        print("         🔍 Basic search...", end=" ", flush=True)
        result_basic = run_asin_lookup(title, author, use_fuzzy=False)
        results_basic.append({**test_case, **result_basic})

        if result_basic["success"]:
            print(f"✅ Found {result_basic['asin']} ({result_basic['elapsed']:.1f}s)")
        else:
            print(f"❌ Failed ({result_basic['elapsed']:.1f}s)")

        print()

        # Rate limiting
        time.sleep(1)

    # Generate summary report
    print("📊 RESULTS SUMMARY")
    print("=" * 60)

    enhanced_success = sum(1 for r in results_enhanced if r["success"])
    basic_success = sum(1 for r in results_basic if r["success"])

    enhanced_avg_time = sum(
        r["elapsed"] for r in results_enhanced if r["success"]
    ) / max(enhanced_success, 1)
    basic_avg_time = sum(r["elapsed"] for r in results_basic if r["success"]) / max(
        basic_success, 1
    )

    print(
        f"Enhanced Search: {enhanced_success}/{len(test_cases)} successful ({enhanced_success / len(test_cases) * 100:.1f}%)"
    )
    print(
        f"Basic Search:    {basic_success}/{len(test_cases)} successful ({basic_success / len(test_cases) * 100:.1f}%)"
    )
    print()
    print(
        f"Success Rate Improvement: +{(enhanced_success - basic_success) / len(test_cases) * 100:.1f} percentage points"
    )
    print(f"Average Time (Enhanced): {enhanced_avg_time:.1f}s")
    print(f"Average Time (Basic):    {basic_avg_time:.1f}s")

    # Show improvement details
    print()
    print("🎯 IMPROVEMENT DETAILS")
    print("=" * 60)

    improvements = 0
    for i, (enhanced, basic) in enumerate(zip(results_enhanced, results_basic)):
        if enhanced["success"] and not basic["success"]:
            improvements += 1
            print(f"✨ Improvement #{improvements}: {enhanced['description']}")
            print(f"   Enhanced found: {enhanced['asin']}")
            print(f"   Basic failed: {basic['stderr'][:100]}...")
            print()

    print(f"Total Cases Where Enhanced Succeeded and Basic Failed: {improvements}")

    if improvements > 0:
        print(
            f"🎉 Enhanced ASIN lookup successfully improved {improvements} challenging cases!"
        )
    else:
        print("ℹ️  Both approaches had similar results on these test cases.")


if __name__ == "__main__":
    main()
