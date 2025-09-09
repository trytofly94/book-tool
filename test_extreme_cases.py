#!/usr/bin/env python3
"""
Test extreme cases that would truly benefit from enhanced ASIN lookup.
These are cases that the basic search might fail on.
"""

import subprocess
import time

# Extreme test cases that should benefit from enhanced search
extreme_cases = [
    # Cases where basic search is likely to fail
    {
        "title": "Final Empire",
        "author": "Sanderson",
        "description": "Very short title/author",
    },
    {"title": "Kings", "author": "B Sanderson", "description": "Minimal title info"},
    {
        "title": "Mistborn Book 1",
        "author": "Brandon",
        "description": "Series indicator + first name only",
    },
    {
        "title": "Elantris Anniversary",
        "author": "Sanderson",
        "description": "Edition indicator",
    },
    {"title": "Way Kings", "author": "Sanderson", "description": "Missing words"},
    # Cases with special characters and formatting
    {
        "title": "Emperor Soul",
        "author": "Sanderson",
        "description": "Missing apostrophe",
    },
    {
        "title": "The Alloy of Law",
        "author": "B.Sanderson",
        "description": "No space in initial",
    },
    {"title": "shadows of self", "author": "sanderson", "description": "All lowercase"},
    # International/translation cases
    {
        "title": "Kinder Nebels",
        "author": "Sanderson",
        "description": "Partial German title",
    },
    {
        "title": "Sturmklaenge",
        "author": "Sanderson",
        "description": "German title variant",
    },
    # Very challenging edge cases
    {
        "title": "Stormlight 1",
        "author": "BS",
        "description": "Series shorthand + initials",
    },
    {
        "title": "Wax Wayne",
        "author": "Sanderson",
        "description": "Character names only",
    },
    {"title": "Cosmere", "author": "Sanderson", "description": "Universe name only"},
]


def run_test(title, author, enhanced=True):
    """Run a single ASIN lookup test."""
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

    if enhanced:
        cmd.extend(["--fuzzy", "--verbose"])
    else:
        cmd.extend(["--no-fuzzy"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        success = "ASIN found:" in result.stdout
        asin = None

        if success:
            for line in result.stdout.split("\n"):
                if "ASIN found:" in line:
                    asin = line.split("ASIN found:")[-1].strip()
                    break

        return success, asin, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        return False, None, "", "Timeout"
    except Exception as e:
        return False, None, "", str(e)


def main():
    """Test extreme cases for ASIN lookup."""
    print("🔥 EXTREME CASE Testing for ASIN Lookup Enhancement")
    print("=" * 65)

    # Clear cache
    subprocess.run(
        ["python3", "-m", "src.calibre_books.cli.main", "asin", "cache", "--clear"],
        capture_output=True,
    )

    enhanced_success = 0
    basic_success = 0
    improvements = []

    for i, case in enumerate(extreme_cases, 1):
        title = case["title"]
        author = case["author"]
        description = case["description"]

        print(f"\n🧪 Test {i:2d}: {description}")
        print(f"         '{title}' by '{author}'")

        # Test enhanced search
        print("         Enhanced: ", end="", flush=True)
        enhanced_ok, enhanced_asin, _, _ = run_test(title, author, enhanced=True)
        if enhanced_ok:
            enhanced_success += 1
            print(f"✅ {enhanced_asin}")
        else:
            print("❌ Failed")

        # Test basic search
        print("         Basic:    ", end="", flush=True)
        basic_ok, basic_asin, _, _ = run_test(title, author, enhanced=False)
        if basic_ok:
            basic_success += 1
            print(f"✅ {basic_asin}")
        else:
            print("❌ Failed")

        # Track improvements
        if enhanced_ok and not basic_ok:
            improvements.append({**case, "asin": enhanced_asin})

        time.sleep(0.5)  # Rate limiting

    # Summary
    print("\n📊 EXTREME CASE RESULTS")
    print("=" * 65)
    print(
        f"Enhanced Search: {enhanced_success}/{len(extreme_cases)} ({enhanced_success / len(extreme_cases) * 100:.1f}%)"
    )
    print(
        f"Basic Search:    {basic_success}/{len(extreme_cases)} ({basic_success / len(extreme_cases) * 100:.1f}%)"
    )
    print(
        f"Improvement:     +{enhanced_success - basic_success} cases (+{(enhanced_success - basic_success) / len(extreme_cases) * 100:.1f} percentage points)"
    )

    if improvements:
        print(
            f"\n🎉 Enhanced search solved {len(improvements)} cases that basic search failed:"
        )
        for imp in improvements:
            print(
                f"   ✨ {imp['description']}: '{imp['title']}' by '{imp['author']}' → {imp['asin']}"
            )
    else:
        print("\n💭 No additional improvements found in extreme cases.")
        print("   This suggests the basic search is already very robust!")


if __name__ == "__main__":
    main()
