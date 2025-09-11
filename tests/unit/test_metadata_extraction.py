"""
Unit tests for metadata extraction from filenames.

Tests the enhanced metadata extraction functionality that handles:
- Traditional patterns like "Author - Title" and "Title by Author"
- New underscore patterns like "author_title"
- Author name expansion and title cleaning
"""

import pytest

from calibre_books.core.file_scanner import FileScanner


class TestMetadataExtraction:
    """Test metadata extraction from various filename patterns."""

    @pytest.fixture
    def file_scanner(self):
        """Create FileScanner instance for testing."""
        # Create minimal config for testing
        config = {"calibre": {"library_path": "~/test-library"}}
        return FileScanner(config)

    def test_traditional_dash_pattern(self, file_scanner):
        """Test extraction from 'Author - Title' pattern."""
        metadata = file_scanner._extract_metadata_from_filename(
            "Brandon Sanderson - Elantris.epub"
        )

        assert metadata.title == "Elantris"
        assert metadata.author == "Brandon Sanderson"

    def test_traditional_by_pattern(self, file_scanner):
        """Test extraction from 'Title by Author' pattern."""
        metadata = file_scanner._extract_metadata_from_filename(
            "Elantris by Brandon Sanderson.epub"
        )

        assert metadata.title == "Elantris"
        assert metadata.author == "Brandon Sanderson"

    def test_traditional_by_pattern_case_insensitive(self, file_scanner):
        """Test 'by' pattern is case insensitive."""
        metadata = file_scanner._extract_metadata_from_filename(
            "Elantris BY Brandon Sanderson.epub"
        )

        assert metadata.title == "Elantris"
        assert metadata.author == "Brandon Sanderson"

    def test_underscore_pattern_known_author(self, file_scanner):
        """Test underscore pattern with known author mapping."""
        metadata = file_scanner._extract_metadata_from_filename(
            "sanderson_elantris.epub"
        )

        assert metadata.title == "Elantris"
        assert metadata.author == "Brandon Sanderson"

    def test_underscore_pattern_unknown_author(self, file_scanner):
        """Test underscore pattern with unknown author (should capitalize)."""
        metadata = file_scanner._extract_metadata_from_filename(
            "unknown_author_great_book.epub"
        )

        # The pattern splits on first underscore: "unknown" + "author_great_book"
        assert metadata.title == "Author Great Book"
        assert metadata.author == "Unknown"

    def test_underscore_pattern_simple_unknown_author(self, file_scanner):
        """Test underscore pattern with simple unknown author."""
        metadata = file_scanner._extract_metadata_from_filename(
            "newauthor_great_book.epub"
        )

        # Should split and capitalize: "newauthor" + "great_book"
        assert metadata.title == "Great Book"
        assert metadata.author == "Newauthor"

    def test_underscore_pattern_with_numbers(self, file_scanner):
        """Test underscore pattern with numbers in title."""
        metadata = file_scanner._extract_metadata_from_filename(
            "sanderson_mistborn1.epub"
        )

        assert metadata.title == "Mistborn 1"
        assert metadata.author == "Brandon Sanderson"

    def test_underscore_pattern_complex_title(self, file_scanner):
        """Test underscore pattern with complex title."""
        metadata = file_scanner._extract_metadata_from_filename(
            "tolkien_the_lord_of_the_rings.epub"
        )

        assert metadata.title == "The Lord Of The Rings"
        assert metadata.author == "J.R.R. Tolkien"

    def test_fallback_to_filename(self, file_scanner):
        """Test fallback when no pattern matches."""
        metadata = file_scanner._extract_metadata_from_filename("randombook.epub")

        # No pattern matches, so uses filename as title
        assert metadata.title == "randombook"
        assert metadata.author == "Unknown"

    def test_multiple_dashes_uses_first_split(self, file_scanner):
        """Test that multiple dashes use first split only."""
        metadata = file_scanner._extract_metadata_from_filename(
            "Author - Title - Subtitle.epub"
        )

        assert metadata.title == "Title - Subtitle"
        assert metadata.author == "Author"

    def test_multiple_underscores_uses_first_split(self, file_scanner):
        """Test that multiple underscores use first split only."""
        metadata = file_scanner._extract_metadata_from_filename(
            "author_title_with_more_words.epub"
        )

        assert metadata.title == "Title With More Words"
        assert metadata.author == "Author"


class TestAuthorNameExpansion:
    """Test author name expansion functionality."""

    @pytest.fixture
    def file_scanner(self):
        """Create FileScanner instance for testing."""
        # Create minimal config for testing
        config = {"calibre": {"library_path": "~/test-library"}}
        return FileScanner(config)

    def test_known_author_mappings(self, file_scanner):
        """Test all known author mappings."""
        known_mappings = {
            "sanderson": "Brandon Sanderson",
            "tolkien": "J.R.R. Tolkien",
            "rowling": "J.K. Rowling",
            "martin": "George R.R. Martin",
            "jordan": "Robert Jordan",
            "hobb": "Robin Hobb",
            "lynch": "Scott Lynch",
            "pratchett": "Terry Pratchett",
            "gaiman": "Neil Gaiman",
            "asimov": "Isaac Asimov",
            "herbert": "Frank Herbert",
            "card": "Orson Scott Card",
            "goodkind": "Terry Goodkind",
            "brooks": "Terry Brooks",
            "butcher": "Jim Butcher",
        }

        for short_name, expected_full in known_mappings.items():
            result = file_scanner._expand_author_name(short_name)
            assert (
                result == expected_full
            ), f"Expected {expected_full}, got {result} for {short_name}"

    def test_unknown_author_capitalization(self, file_scanner):
        """Test capitalization of unknown authors."""
        test_cases = [
            ("unknown", "Unknown"),
            ("john_doe", "John Doe"),
            ("first_middle_last", "First Middle Last"),
            ("singleword", "Singleword"),
        ]

        for input_name, expected in test_cases:
            result = file_scanner._expand_author_name(input_name)
            assert (
                result == expected
            ), f"Expected {expected}, got {result} for {input_name}"

    def test_case_insensitive_mapping(self, file_scanner):
        """Test that author mapping is case insensitive."""
        test_cases = [
            ("SANDERSON", "Brandon Sanderson"),
            ("Tolkien", "J.R.R. Tolkien"),
            ("MaRtIn", "George R.R. Martin"),
        ]

        for input_name, expected in test_cases:
            result = file_scanner._expand_author_name(input_name)
            assert (
                result == expected
            ), f"Expected {expected}, got {result} for {input_name}"


class TestTitleCleaning:
    """Test title cleaning functionality."""

    @pytest.fixture
    def file_scanner(self):
        """Create FileScanner instance for testing."""
        # Create minimal config for testing
        config = {"calibre": {"library_path": "~/test-library"}}
        return FileScanner(config)

    def test_underscore_replacement(self, file_scanner):
        """Test underscores are replaced with spaces."""
        test_cases = [
            ("the_lord_of_the_rings", "The Lord Of The Rings"),
            ("a_song_of_ice_and_fire", "A Song Of Ice And Fire"),
            ("single_word", "Single Word"),
        ]

        for input_title, expected in test_cases:
            result = file_scanner._clean_title(input_title)
            assert (
                result == expected
            ), f"Expected {expected}, got {result} for {input_title}"

    def test_number_pattern_handling(self, file_scanner):
        """Test number patterns are handled correctly."""
        test_cases = [
            ("mistborn1", "Mistborn 1"),
            ("book2oftheseries", "Book 2 Oftheseries"),
            ("series1book2", "Series 1 Book 2"),
            ("foundation3", "Foundation 3"),
        ]

        for input_title, expected in test_cases:
            result = file_scanner._clean_title(input_title)
            assert (
                result == expected
            ), f"Expected {expected}, got {result} for {input_title}"

    def test_hyphen_handling(self, file_scanner):
        """Test hyphen spacing is normalized."""
        test_cases = [
            ("word-word", "Word - Word"),  # All hyphens get spaces
            ("word - word", "Word - Word"),
            ("word-  word", "Word - Word"),
            ("word   -word", "Word - Word"),
        ]

        for input_title, expected in test_cases:
            result = file_scanner._clean_title(input_title)
            assert (
                result == expected
            ), f"Expected {expected}, got {result} for {input_title}"

    def test_capitalization(self, file_scanner):
        """Test proper capitalization of words."""
        test_cases = [
            ("the hobbit", "The Hobbit"),
            ("a song of ice", "A Song Of Ice"),
            ("lord of the rings", "Lord Of The Rings"),
        ]

        for input_title, expected in test_cases:
            result = file_scanner._clean_title(input_title)
            assert (
                result == expected
            ), f"Expected {expected}, got {result} for {input_title}"

    def test_complex_title_patterns(self, file_scanner):
        """Test complex title patterns with multiple elements."""
        test_cases = [
            ("the_wheel_of_time_book1", "The Wheel Of Time Book 1"),
            (
                "lord_of_the_rings-fellowship",
                "Lord Of The Rings - Fellowship",
            ),  # Hyphen gets spaces
            (
                "game_of_thrones_book2_clash_of_kings",
                "Game Of Thrones Book 2 Clash Of Kings",
            ),
        ]

        for input_title, expected in test_cases:
            result = file_scanner._clean_title(input_title)
            assert (
                result == expected
            ), f"Expected {expected}, got {result} for {input_title}"


class TestRealWorldScenarios:
    """Test realistic filename scenarios."""

    @pytest.fixture
    def file_scanner(self):
        """Create FileScanner instance for testing."""
        # Create minimal config for testing
        config = {"calibre": {"library_path": "~/test-library"}}
        return FileScanner(config)

    def test_sanderson_books(self, file_scanner):
        """Test various Sanderson book filenames."""
        test_cases = [
            ("sanderson_elantris.epub", "Elantris", "Brandon Sanderson"),
            ("sanderson_mistborn1.epub", "Mistborn 1", "Brandon Sanderson"),
            (
                "sanderson_the_way_of_kings.epub",
                "The Way Of Kings",
                "Brandon Sanderson",
            ),
            ("sanderson_warbreaker.epub", "Warbreaker", "Brandon Sanderson"),
        ]

        for filename, expected_title, expected_author in test_cases:
            metadata = file_scanner._extract_metadata_from_filename(filename)
            assert metadata.title == expected_title, f"Title mismatch for {filename}"
            assert metadata.author == expected_author, f"Author mismatch for {filename}"

    def test_mixed_formats(self, file_scanner):
        """Test different file formats work the same way."""
        base_filename = "tolkien_the_hobbit"
        expected_title = "The Hobbit"
        expected_author = "J.R.R. Tolkien"

        formats = [".epub", ".mobi", ".azw3", ".pdf"]

        for format_ext in formats:
            filename = base_filename + format_ext
            metadata = file_scanner._extract_metadata_from_filename(filename)
            assert metadata.title == expected_title, f"Title mismatch for {filename}"
            assert metadata.author == expected_author, f"Author mismatch for {filename}"

    def test_priority_of_patterns(self, file_scanner):
        """Test that patterns are applied in correct priority order."""
        # Dash pattern should take precedence over underscore
        metadata = file_scanner._extract_metadata_from_filename(
            "Author Name - Book_Title_With_Underscores.epub"
        )
        assert metadata.title == "Book_Title_With_Underscores"
        assert metadata.author == "Author Name"

        # 'by' pattern should take precedence over underscore
        metadata = file_scanner._extract_metadata_from_filename(
            "Book_Title by Author_Name.epub"
        )
        assert metadata.title == "Book_Title"
        assert metadata.author == "Author_Name"

    def test_edge_cases(self, file_scanner):
        """Test edge cases and boundary conditions."""
        # Empty parts - should fall back to filename
        metadata = file_scanner._extract_metadata_from_filename("_.epub")
        assert metadata.title == "_"
        assert metadata.author == "Unknown"

        # Empty author part - should fall back to filename
        metadata = file_scanner._extract_metadata_from_filename("_great_book.epub")
        assert metadata.title == "_great_book"
        assert metadata.author == "Unknown"

        # Empty title part - should fall back to filename
        metadata = file_scanner._extract_metadata_from_filename("author_.epub")
        assert metadata.title == "author_"
        assert metadata.author == "Unknown"

        # Very long filename with underscore pattern
        long_filename = "author_" + "_".join(["word"] * 20) + ".epub"
        metadata = file_scanner._extract_metadata_from_filename(long_filename)
        assert metadata.author == "Author"
        assert "Word" in metadata.title

    def test_backward_compatibility(self, file_scanner):
        """Test that existing patterns still work exactly as before."""
        # Traditional dash pattern
        metadata = file_scanner._extract_metadata_from_filename(
            "J.R.R. Tolkien - The Lord of the Rings.epub"
        )
        assert metadata.title == "The Lord of the Rings"
        assert metadata.author == "J.R.R. Tolkien"

        # Traditional by pattern
        metadata = file_scanner._extract_metadata_from_filename(
            "Dune by Frank Herbert.epub"
        )
        assert metadata.title == "Dune"
        assert metadata.author == "Frank Herbert"

        # No pattern fallback
        metadata = file_scanner._extract_metadata_from_filename(
            "SomeRandomBookName.epub"
        )
        assert metadata.title == "SomeRandomBookName"
        assert metadata.author == "Unknown"
