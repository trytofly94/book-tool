#!/usr/bin/env python3
"""
Localization Metadata Extractor for Enhanced ASIN Lookup
Extracts titles and language information from books to support multi-language ASIN lookups
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LocalizationMetadataExtractor:
    """
    Enhanced metadata extractor that focuses on localization information
    for improved ASIN lookup accuracy with non-English books
    """

    def __init__(self):
        # Common language code mappings
        self.language_mappings = {
            "de": {"name": "German", "amazon_domain": "amazon.de"},
            "fr": {"name": "French", "amazon_domain": "amazon.fr"},
            "es": {"name": "Spanish", "amazon_domain": "amazon.es"},
            "it": {"name": "Italian", "amazon_domain": "amazon.it"},
            "en": {"name": "English", "amazon_domain": "amazon.com"},
            "deu": {
                "name": "German",
                "amazon_domain": "amazon.de",
            },  # Alternative German code
            "eng": {
                "name": "English",
                "amazon_domain": "amazon.com",
            },  # Alternative English code
        }

        # Title pattern analysis for known book series (can be expanded)
        self.title_patterns = {
            "mistborn": {
                "english": [
                    "Mistborn",
                    "The Final Empire",
                    "The Well of Ascension",
                    "The Hero of Ages",
                ],
                "german": [
                    "Kinder des Nebels",
                    "Krieger des Feuers",
                    "Herrscher des Lichts",
                ],
            },
            "stormlight": {
                "english": [
                    "The Way of Kings",
                    "Words of Radiance",
                    "Oathbringer",
                    "Rhythm of War",
                ],
                "german": ["Der Weg der Könige", "Pfad der Winde", "Schwurträger"],
            },
            "skyward": {
                "english": ["Skyward", "Starsight", "Cytonic", "Defiant"],
                "german": ["Ruf der Sterne", "Sternensicht"],
            },
        }

    def extract_from_epub(self, epub_path: str) -> Dict[str, str]:
        """
        Extract enhanced metadata from EPUB file
        Focus on title and language information for localization
        """
        metadata = {
            "title": "",
            "language": "",
            "author": "",
            "original_title": "",  # For storing alternate titles
            "series": "",
            "series_index": "",
        }

        try:
            with zipfile.ZipFile(epub_path, "r") as epub:
                # Read container.xml to find OPF file
                container_content = epub.read("META-INF/container.xml")
                container_tree = ET.fromstring(container_content)

                # Find OPF file path
                ns = {"container": "urn:oasis:names:tc:opendocument:xmlns:container"}
                opf_path = container_tree.find(".//container:rootfile", ns).get(
                    "full-path"
                )

                # Read OPF file
                opf_content = epub.read(opf_path)
                opf_tree = ET.fromstring(opf_content)

                # Define namespaces
                namespaces = {
                    "dc": "http://purl.org/dc/elements/1.1/",
                    "opf": "http://www.idpf.org/2007/opf",
                }

                # Extract title
                title_elem = opf_tree.find(".//dc:title", namespaces)
                if title_elem is not None:
                    metadata["title"] = title_elem.text.strip()

                # Extract language
                lang_elem = opf_tree.find(".//dc:language", namespaces)
                if lang_elem is not None:
                    metadata["language"] = lang_elem.text.strip()

                # Extract author
                creator_elem = opf_tree.find(".//dc:creator", namespaces)
                if creator_elem is not None:
                    metadata["author"] = creator_elem.text.strip()

                # Extract series information from meta tags
                for meta_elem in opf_tree.findall(".//meta", namespaces):
                    name = meta_elem.get("name", "").lower()
                    content = meta_elem.get("content", "")

                    if name == "calibre:series":
                        metadata["series"] = content
                    elif name == "calibre:series_index":
                        metadata["series_index"] = content

                # Try to extract series info from title if not in meta
                if not metadata["series"]:
                    series_info = self._extract_series_from_title(metadata["title"])
                    metadata.update(series_info)

                logger.info(
                    f"Extracted metadata from {os.path.basename(epub_path)}: "
                    f"Title='{metadata['title']}', Language='{metadata['language']}'"
                )

        except Exception as e:
            logger.error(f"Error extracting metadata from {epub_path}: {e}")

        return metadata

    def extract_from_mobi(self, mobi_path: str) -> Dict[str, str]:
        """
        Extract metadata from MOBI file
        Basic implementation - MOBI parsing is more complex
        """
        metadata = {
            "title": "",
            "language": "",
            "author": "",
            "original_title": "",
            "series": "",
            "series_index": "",
        }

        # For now, try to extract from filename as fallback
        filename = os.path.basename(mobi_path)
        metadata.update(self._extract_from_filename(filename))

        logger.info(f"Extracted metadata from MOBI {filename} (filename-based)")
        return metadata

    def extract_from_filename(self, filepath: str) -> Dict[str, str]:
        """
        Extract metadata from filename as fallback method
        Useful for files where metadata extraction fails
        """
        filename = os.path.basename(filepath)
        return self._extract_from_filename(filename)

    def _extract_from_filename(self, filename: str) -> Dict[str, str]:
        """
        Helper method to extract metadata from filename patterns
        """
        metadata = {
            "title": "",
            "language": "",
            "author": "",
            "original_title": "",
            "series": "",
            "series_index": "",
        }

        # Remove file extension
        base_name = os.path.splitext(filename)[0]

        # Common patterns for Brandon Sanderson books
        patterns = [
            # Pattern: author_series_title.ext
            r"([^_]+)_([^_]+)_(.+)",
            # Pattern: author_title.ext
            r"([^_]+)_(.+)",
        ]

        for pattern in patterns:
            match = re.match(pattern, base_name)
            if match:
                if len(match.groups()) == 3:
                    author, series, title = match.groups()
                    metadata["author"] = author.replace("-", " ").title()
                    metadata["series"] = series.replace("-", " ").title()
                    metadata["title"] = title.replace("-", " ").title()
                elif len(match.groups()) == 2:
                    author, title = match.groups()
                    metadata["author"] = author.replace("-", " ").title()
                    metadata["title"] = title.replace("-", " ").title()
                break

        # Try to determine language from title patterns
        metadata["language"] = self._guess_language_from_title(metadata["title"])

        return metadata

    def _extract_series_from_title(self, title: str) -> Dict[str, str]:
        """
        Extract series information from title string
        """
        series_info = {"series": "", "series_index": ""}

        # Common patterns for series information
        patterns = [
            r"^(.+?)\s+(\d+)\s*-\s*(.+)$",  # "Series 01 - Title"
            r"^(.+?)\s+Book\s+(\d+):\s*(.+)$",  # "Series Book 1: Title"
            r"^(.+?)\s+\((\d+)\):\s*(.+)$",  # "Series (1): Title"
        ]

        for pattern in patterns:
            match = re.match(pattern, title)
            if match:
                series_info["series"] = match.group(1).strip()
                series_info["series_index"] = match.group(2)
                # Update title to just the book title
                series_info["title"] = match.group(3).strip()
                break

        return series_info

    def _guess_language_from_title(self, title: str) -> str:
        """
        Guess language from title patterns
        """
        if not title:
            return "en"  # Default to English

        title_lower = title.lower()

        # German indicators
        german_indicators = [
            "kinder des",
            "der weg",
            "krieger des",
            "herrscher des",
            "ruf der",
            "pfad der",
        ]
        if any(indicator in title_lower for indicator in german_indicators):
            return "de"

        # French indicators
        french_indicators = ["le chemin", "les enfants", "l'empire"]
        if any(indicator in title_lower for indicator in french_indicators):
            return "fr"

        # Default to English
        return "en"

    def get_localized_search_terms(
        self, metadata: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """
        Generate search terms optimized for different regions/languages with comprehensive fallback mechanisms
        Returns list of search term dictionaries with appropriate Amazon domains
        """
        search_terms = []

        title = metadata.get("title", "")
        author = metadata.get("author", "")
        language = metadata.get("language", "en")
        series = metadata.get("series", "")

        # Handle case where title is empty (corrupted metadata)
        if not title:
            logger.warning("No title found in metadata, using fallback strategies")
            if series:
                title = series  # Use series name as title fallback
            elif author:
                title = author  # Last resort: use author name
            else:
                return []  # Can't search without any text

        # Normalize language code with fallbacks
        lang_code = self._normalize_language_code(language)

        # === PRIMARY SEARCHES ===

        # 1. Primary search with detected language and localized title
        if lang_code in self.language_mappings:
            search_terms.append(
                {
                    "title": title,
                    "author": author,
                    "language": lang_code,
                    "amazon_domain": self.language_mappings[lang_code]["amazon_domain"],
                    "priority": 1,
                    "strategy": "localized_primary",
                }
            )

        # 2. English equivalent search (if not already English)
        if lang_code != "en":
            english_title = self._find_english_equivalent(title, author)
            if english_title:
                search_terms.append(
                    {
                        "title": english_title,
                        "author": author,
                        "language": "en",
                        "amazon_domain": "amazon.com",
                        "priority": 2,
                        "strategy": "english_equivalent",
                    }
                )

        # === FALLBACK SEARCHES ===

        # 3. Series-based search (if available)
        if series and series.strip():
            search_terms.append(
                {
                    "title": f"{series} {author}",
                    "author": author,
                    "language": lang_code,
                    "amazon_domain": self.language_mappings.get(lang_code, {}).get(
                        "amazon_domain", "amazon.com"
                    ),
                    "priority": 3,
                    "strategy": "series_based",
                }
            )

            # Also try series-based English search
            if lang_code != "en":
                search_terms.append(
                    {
                        "title": f"{series} {author}",
                        "author": author,
                        "language": "en",
                        "amazon_domain": "amazon.com",
                        "priority": 4,
                        "strategy": "series_english",
                    }
                )

        # 4. Author-only search (last resort)
        if author:
            search_terms.append(
                {
                    "title": author,
                    "author": author,
                    "language": "en",
                    "amazon_domain": "amazon.com",
                    "priority": 5,
                    "strategy": "author_only",
                }
            )

        # 5. Title variations (clean, simplified titles)
        cleaned_title = self._clean_title_for_search(title)
        if cleaned_title != title:
            search_terms.append(
                {
                    "title": cleaned_title,
                    "author": author,
                    "language": lang_code,
                    "amazon_domain": self.language_mappings.get(lang_code, {}).get(
                        "amazon_domain", "amazon.com"
                    ),
                    "priority": 6,
                    "strategy": "cleaned_title",
                }
            )

        # 6. Cross-language fallbacks for common languages
        cross_language_domains = self._get_cross_language_fallbacks(lang_code)
        for i, domain in enumerate(cross_language_domains):
            search_terms.append(
                {
                    "title": title,
                    "author": author,
                    "language": domain.split(".")[1] if "." in domain else "en",
                    "amazon_domain": domain,
                    "priority": 7 + i,
                    "strategy": f"cross_language_{domain}",
                }
            )

        # Sort by priority and return
        search_terms.sort(key=lambda x: x["priority"])
        return search_terms

    def _normalize_language_code(self, language: str) -> str:
        """
        Normalize and validate language codes with fallbacks
        """
        if not language:
            return "en"  # Default to English

        lang_code = language.lower().strip()

        # Handle common variations
        if lang_code in ["deu", "ger"]:
            return "de"
        elif lang_code in ["eng"]:
            return "en"
        elif lang_code in ["fra", "fre"]:
            return "fr"
        elif lang_code in ["spa"]:
            return "es"
        elif lang_code in ["ita"]:
            return "it"

        # Return as-is if it's a known code
        if lang_code in self.language_mappings:
            return lang_code

        # Default fallback
        return "en"

    def _clean_title_for_search(self, title: str) -> str:
        """
        Clean title for better search results
        Remove common noise words and formatting
        """
        if not title:
            return title

        # Remove series numbers and markers
        cleaned = re.sub(r"\s+(0?\d+)\s*[-–]\s*", " ", title)

        # Remove parenthetical information
        cleaned = re.sub(r"\([^)]*\)", "", cleaned)

        # Remove brackets
        cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)

        # Clean up whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def _get_cross_language_fallbacks(self, primary_language: str) -> List[str]:
        """
        Get cross-language fallback domains based on primary language
        """
        # Define fallback chains based on language relationships
        fallback_chains = {
            "de": ["amazon.com"],  # German -> English
            "fr": ["amazon.com"],  # French -> English
            "es": ["amazon.com"],  # Spanish -> English
            "it": ["amazon.com"],  # Italian -> English
            "en": ["amazon.de", "amazon.fr"],  # English -> German, French
        }

        return fallback_chains.get(primary_language, ["amazon.com"])

    def _find_english_equivalent(self, title: str, author: str = "") -> Optional[str]:
        """
        Try to find English equivalent of a localized title
        Uses pattern matching for known book series
        """
        title_lower = title.lower()

        for series, translations in self.title_patterns.items():
            # Check if this title matches a known translation
            for lang, titles in translations.items():
                if lang != "english":
                    for i, translated_title in enumerate(titles):
                        if (
                            translated_title.lower() in title_lower
                            or title_lower in translated_title.lower()
                        ):
                            # Found a match, return corresponding English title
                            english_titles = translations.get("english", [])
                            if i < len(english_titles):
                                return english_titles[i]

        return None

    def extract_metadata_from_path(self, file_path: str) -> Dict[str, str]:
        """
        Main method to extract metadata from any supported file type with robust error handling
        """
        # Initialize empty metadata for fallback
        fallback_metadata = {
            "title": "",
            "language": "",
            "author": "",
            "original_title": "",
            "series": "",
            "series_index": "",
        }

        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            # Still try filename extraction even if file doesn't exist
            return self.extract_from_filename(file_path)

        file_extension = Path(file_path).suffix.lower()
        filename = os.path.basename(file_path)

        # Try to extract from file content first
        try:
            if file_extension == ".epub":
                metadata = self.extract_from_epub(file_path)
                if self._is_metadata_valid(metadata):
                    logger.info(f"Successfully extracted EPUB metadata from {filename}")
                    return metadata
                else:
                    logger.warning(
                        f"Invalid EPUB metadata extracted from {filename}, trying filename fallback"
                    )

            elif file_extension in [".mobi", ".azw", ".azw3"]:
                metadata = self.extract_from_mobi(file_path)
                if self._is_metadata_valid(metadata):
                    logger.info(f"Successfully extracted MOBI metadata from {filename}")
                    return metadata
                else:
                    logger.warning(
                        f"Invalid MOBI metadata extracted from {filename}, trying filename fallback"
                    )
            else:
                logger.warning(
                    f"Unsupported file type: {file_extension}. Using filename extraction."
                )

        except Exception as e:
            logger.error(f"Error extracting metadata from {file_path}: {e}")
            # Check if this might be a corrupted file
            if self._is_likely_corrupted(file_path, e):
                logger.warning(
                    f"File {filename} appears to be corrupted or not a valid {file_extension} file"
                )

        # Fallback to filename extraction
        logger.info(f"Using filename-based extraction for {filename}")
        filename_metadata = self.extract_from_filename(file_path)

        # Merge filename metadata with any partial file metadata
        if "metadata" in locals() and metadata:
            return self._merge_metadata(metadata, filename_metadata)
        else:
            return filename_metadata

    def _is_metadata_valid(self, metadata: Dict[str, str]) -> bool:
        """
        Check if extracted metadata contains meaningful information
        """
        if not metadata:
            return False

        # Must have at least title or author
        title = metadata.get("title", "").strip()
        author = metadata.get("author", "").strip()

        if not title and not author:
            return False

        # Check for obviously corrupted data
        if title and len(title) < 2:  # Title too short
            return False

        if author and len(author) < 2:  # Author name too short
            return False

        return True

    def _is_likely_corrupted(self, file_path: str, error: Exception) -> bool:
        """
        Determine if a file is likely corrupted based on error patterns
        """
        error_str = str(error).lower()

        # Common corruption indicators
        corruption_indicators = [
            "not a zip file",
            "bad zipfile",
            "corrupt",
            "invalid",
            "unexpected eof",
            "file is not a zip file",
            "bad magic number",
        ]

        if any(indicator in error_str for indicator in corruption_indicators):
            return True

        # Check file size (too small files are likely corrupted)
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 1024:  # Less than 1KB is suspicious for an ebook
                return True
        except OSError:
            pass

        return False

    def _merge_metadata(
        self, primary: Dict[str, str], fallback: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Merge two metadata dictionaries, using primary when available, fallback otherwise
        """
        merged = {}

        for key in [
            "title",
            "language",
            "author",
            "original_title",
            "series",
            "series_index",
        ]:
            primary_value = primary.get(key, "").strip()
            fallback_value = fallback.get(key, "").strip()

            # Use primary if it has content, otherwise use fallback
            merged[key] = primary_value if primary_value else fallback_value

        return merged


def test_localization_extractor():
    """Test the localization metadata extractor with sample files including fallback mechanisms"""
    extractor = LocalizationMetadataExtractor()

    print("=== Testing Enhanced Localization Metadata Extractor with Fallbacks ===")

    # Test files from the pipeline directory
    test_files = [
        "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/sanderson_mistborn1_kinder-des-nebels.epub",
        "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/sanderson_sturmlicht1_weg-der-koenige.epub",  # Known corrupted
        "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/sanderson_skyward1_ruf-der-sterne.epub",
    ]

    for test_file in test_files:
        filename = os.path.basename(test_file)
        print(f"\n{'='*60}")
        print(f"Testing: {filename}")
        print(f"{'='*60}")

        # Test metadata extraction with fallback mechanisms
        metadata = extractor.extract_metadata_from_path(test_file)

        print(f"✓ Extracted Metadata:")
        print(f"  Title: {metadata.get('title', 'N/A')}")
        print(f"  Language: {metadata.get('language', 'N/A')}")
        print(f"  Author: {metadata.get('author', 'N/A')}")
        print(f"  Series: {metadata.get('series', 'N/A')}")

        # Test fallback search terms generation
        if metadata and (metadata.get("title") or metadata.get("author")):
            print(f"\n✓ Generated Search Terms (with fallbacks):")
            search_terms = extractor.get_localized_search_terms(metadata)

            for i, term in enumerate(search_terms[:8], 1):  # Show first 8 search terms
                strategy = term.get("strategy", "unknown")
                priority = term.get("priority", "?")
                print(
                    f"  {i}. [{strategy}] P{priority}: '{term['title']}' by {term['author']} "
                    f"({term['language']}) -> {term['amazon_domain']}"
                )

            if len(search_terms) > 8:
                print(f"  ... and {len(search_terms) - 8} more fallback strategies")
        else:
            print("✗ No usable metadata extracted")

    # Test edge cases
    print(f"\n{'='*60}")
    print("Testing Edge Cases")
    print(f"{'='*60}")

    # Test with non-existent file
    print("\n--- Non-existent file test ---")
    fake_file = "/nonexistent/sanderson_test_book.epub"
    metadata = extractor.extract_metadata_from_path(fake_file)
    print(f"Non-existent file metadata: {metadata}")

    # Test with empty metadata
    print("\n--- Empty metadata fallback test ---")
    empty_metadata = {}
    search_terms = extractor.get_localized_search_terms(empty_metadata)
    print(f"Empty metadata search terms: {len(search_terms)} terms generated")

    # Test language code normalization
    print("\n--- Language code normalization test ---")
    test_languages = ["deu", "ger", "eng", "fra", "spa", "ita", "unknown", ""]
    for lang in test_languages:
        normalized = extractor._normalize_language_code(lang)
        print(f"  {lang} -> {normalized}")

    print(f"\n{'='*60}")
    print("✓ Enhanced fallback testing completed")
    print(f"{'='*60}")


if __name__ == "__main__":
    test_localization_extractor()
