"""
ASIN lookup service for Calibre Books CLI.

This module provides functionality for looking up Amazon ASINs
from various sources including Amazon, Goodreads, and OpenLibrary.

Enhanced with improved series handling, fuzzy matching, and additional search strategies
as part of Issue #55 improvements.

Integrates the enhanced_asin_lookup.py functionality into the new CLI architecture.
"""

import requests
import time
import re
import json
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import concurrent.futures
from bs4 import BeautifulSoup

# For fuzzy matching functionality
try:
    from fuzzywuzzy import fuzz

    FUZZY_AVAILABLE = True
except ImportError:
    try:
        from difflib import SequenceMatcher

        FUZZY_AVAILABLE = True
    except ImportError:
        FUZZY_AVAILABLE = False

from ..utils.logging import LoggerMixin
from .book import Book, ASINLookupResult

if TYPE_CHECKING:
    from ..config.manager import ConfigManager


class ASINLookupService(LoggerMixin):
    """
    ASIN lookup service.

    Provides methods for looking up ASINs from multiple sources
    with caching and rate limiting.
    """

    def __init__(self, config_manager: "ConfigManager"):
        """
        Initialize ASIN lookup service.

        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        super().__init__()
        self.config_manager = config_manager

        # Get ASIN lookup specific configuration with error handling
        try:
            asin_config = config_manager.get_asin_config()
            cache_path_config = asin_config.get(
                "cache_path", "~/.book-tool/asin_cache.db"
            )
            # Ensure SQLite cache uses .db extension
            if cache_path_config.endswith(".json"):
                cache_path_config = cache_path_config.replace(".json", ".db")
            self.cache_path = Path(cache_path_config).expanduser()
            self.sources = asin_config.get(
                "sources", ["amazon", "goodreads", "openlibrary"]
            )
            self.rate_limit = asin_config.get("rate_limit", 2.0)

            self.logger.debug(
                f"Initialized ASIN lookup with sources: {self.sources}, cache: {self.cache_path}"
            )
        except Exception as e:
            self.logger.warning(f"Failed to load ASIN config, using defaults: {e}")
            self.cache_path = Path("~/.book-tool/asin_cache.db").expanduser()
            self.sources = ["amazon", "goodreads", "openlibrary"]
            self.rate_limit = 2.0

        self.logger.info(
            f"Initialized ASIN lookup service with sources: {self.sources}"
        )

        # Initialize cache manager with SQLite backend
        from .cache import SQLiteCacheManager

        self.cache_manager = SQLiteCacheManager(self.cache_path)

        # User agents for web scraping - updated for 2025
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        ]

        # Thread lock for cache operations
        self._cache_lock = threading.Lock()

        # Enhanced search settings (Issue #55)
        self.fuzzy_threshold = 80  # Minimum similarity score (0-100)
        self.enable_series_variations = True
        self.enable_fuzzy_matching = FUZZY_AVAILABLE

        # Known series patterns for Brandon Sanderson and other popular authors
        self.series_patterns = {
            "mistborn": [
                "Mistborn: The Final Empire",
                "The Final Empire",
                "Mistborn 1",
            ],
            "stormlight": [
                "The Way of Kings",
                "Words of Radiance",
                "Oathbringer",
                "Rhythm of War",
                "Knights of Wind and Truth",
            ],
            "elantris": [
                "Elantris: Tenth Anniversary",
                "Elantris: Author's Definitive Edition",
            ],
            "warbreaker": ["Warbreaker"],
            "skyward": ["Skyward", "Starsight", "Cytonic", "Defiant"],
            "wax and wayne": [
                "The Alloy of Law",
                "Shadows of Self",
                "The Bands of Mourning",
                "The Lost Metal",
            ],
        }

        # Common title variations and normalization patterns
        self.title_variations = {
            "articles": ["the", "a", "an"],
            "separators": [":", " - ", " – ", " — "],
            "series_indicators": [
                "book 1",
                "book one",
                "volume 1",
                "volume one",
                "#1",
                "part 1",
                "part one",
            ],
            "edition_indicators": [
                "anniversary",
                "definitive",
                "special",
                "limited",
                "collector's",
            ],
        }

    def _generate_title_variations(
        self, title: str, author: Optional[str] = None
    ) -> List[str]:
        """
        Generate multiple title variations for improved search success rate.

        Args:
            title: Original book title
            author: Book author (used for series context)

        Returns:
            List of title variations to try
        """
        variations = [title]  # Start with original title

        if not self.enable_series_variations:
            return variations

        title_lower = title.lower().strip()

        # 1. Remove common articles from the beginning
        for article in self.title_variations["articles"]:
            if title_lower.startswith(f"{article} "):
                no_article = title[len(article) :].strip()
                variations.append(no_article)
                # Also add back with "The" if original didn't have it
                if article != "the":
                    variations.append(f"The {no_article}")

        # 2. Add series context for known patterns
        if author and "sanderson" in author.lower():
            for series_key, series_titles in self.series_patterns.items():
                # Check if current title matches any known series title
                for series_title in series_titles:
                    if self._fuzzy_match(title, series_title, threshold=70):
                        # Add all variations from this series
                        variations.extend(series_titles)
                        break

                # Check if title contains series keywords
                if series_key.replace(" ", "").lower() in title_lower.replace(" ", ""):
                    variations.extend(series_titles)

        # 3. Handle common title formats and separators
        for separator in self.title_variations["separators"]:
            if separator in title:
                # Split on separator and try variations
                parts = title.split(separator, 1)
                if len(parts) == 2:
                    main_title, subtitle = parts[0].strip(), parts[1].strip()
                    variations.extend(
                        [
                            main_title,  # Just the main part
                            subtitle,  # Just the subtitle
                            f"{main_title} {subtitle}",  # Space-separated
                            f"{subtitle} ({main_title})",  # Reversed with parentheses
                        ]
                    )

        # 4. Remove series indicators
        for indicator in self.title_variations["series_indicators"]:
            if indicator in title_lower:
                clean_title = re.sub(
                    re.escape(indicator), "", title, flags=re.IGNORECASE
                ).strip()
                clean_title = re.sub(
                    r"\s+", " ", clean_title
                )  # Clean up multiple spaces
                if clean_title and clean_title not in variations:
                    variations.append(clean_title)

        # 5. Remove edition indicators
        for indicator in self.title_variations["edition_indicators"]:
            if indicator in title_lower:
                clean_title = re.sub(
                    f"\\b{re.escape(indicator)}\\b.*", "", title, flags=re.IGNORECASE
                ).strip()
                clean_title = re.sub(
                    r"\s+", " ", clean_title
                )  # Clean up multiple spaces
                if clean_title and clean_title not in variations:
                    variations.append(clean_title)

        # 6. Remove parenthetical information
        paren_removed = re.sub(r"\([^)]*\)", "", title).strip()
        paren_removed = re.sub(r"\s+", " ", paren_removed)
        if paren_removed and paren_removed not in variations:
            variations.append(paren_removed)

        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for variation in variations:
            variation_clean = variation.strip()
            if variation_clean and variation_clean not in seen:
                seen.add(variation_clean)
                unique_variations.append(variation_clean)

        return unique_variations

    def _fuzzy_match(self, text1: str, text2: str, threshold: int = 80) -> bool:
        """
        Check if two strings are similar using fuzzy matching.

        Args:
            text1: First string
            text2: Second string
            threshold: Minimum similarity score (0-100)

        Returns:
            True if strings are similar enough
        """
        if not self.enable_fuzzy_matching:
            return text1.lower().strip() == text2.lower().strip()

        try:
            if FUZZY_AVAILABLE and "fuzz" in globals():
                # Use fuzzywuzzy if available
                similarity = fuzz.ratio(text1.lower().strip(), text2.lower().strip())
            else:
                # Fallback to difflib SequenceMatcher
                matcher = SequenceMatcher(
                    None, text1.lower().strip(), text2.lower().strip()
                )
                similarity = matcher.ratio() * 100

            return similarity >= threshold
        except Exception:
            # If fuzzy matching fails, fall back to exact match
            return text1.lower().strip() == text2.lower().strip()

    def _normalize_author_name(self, author: str) -> List[str]:
        """
        Generate variations of author names for better matching.

        Args:
            author: Original author name

        Returns:
            List of author name variations
        """
        variations = [author]

        # Common author name patterns
        # "Brandon Sanderson" -> ["Brandon Sanderson", "B. Sanderson", "Sanderson", "Sanderson, Brandon"]

        if " " in author:
            parts = author.split()
            if len(parts) == 2:
                first, last = parts
                variations.extend(
                    [
                        f"{first[0]}. {last}",  # B. Sanderson
                        last,  # Sanderson
                        f"{last}, {first}",  # Sanderson, Brandon
                    ]
                )
            elif len(parts) > 2:
                # Handle middle names/initials
                first = parts[0]
                last = parts[-1]
                variations.extend(
                    [
                        f"{first} {last}",  # Brandon Sanderson (remove middle)
                        f"{first[0]}. {last}",  # B. Sanderson
                        last,  # Sanderson
                    ]
                )

        return list(set(variations))  # Remove duplicates

    def lookup_by_title(
        self,
        title: str,
        author: Optional[str] = None,
        sources: Optional[List[str]] = None,
        use_cache: bool = True,
        progress_callback=None,
        verbose: bool = False,
    ) -> ASINLookupResult:
        """
        Look up ASIN by book title and author.

        Args:
            title: Book title
            author: Book author (optional)
            sources: Sources to use for lookup
            use_cache: Whether to use cached results
            progress_callback: Progress callback function

        Returns:
            ASIN lookup result
        """
        start_time = time.time()
        self.logger.info(
            f"Looking up ASIN for '{title}' by {author or 'unknown author'}"
        )

        if progress_callback:
            progress_callback(description="Starting ASIN lookup...")

        # Generate title variations for enhanced search (Issue #55)
        title_variations = self._generate_title_variations(title, author)
        author_variations = self._normalize_author_name(author) if author else [None]

        if verbose:
            self.logger.info(
                f"Generated {len(title_variations)} title variations: {title_variations}"
            )
            if author:
                self.logger.info(
                    f"Generated {len(author_variations)} author variations: {author_variations}"
                )

        # Create cache key using original title/author
        cache_key = f"{title}_{author or ''}".lower().strip()

        # Check cache first if enabled
        if use_cache:
            cached_asin = self.cache_manager.get_cached_asin(cache_key)
            if cached_asin:
                self.logger.info(f"Cache hit for: {cache_key}")
                return ASINLookupResult(
                    query_title=title,
                    query_author=author,
                    asin=cached_asin,
                    metadata=None,
                    source="cache",
                    success=True,
                    lookup_time=time.time() - start_time,
                    from_cache=True,
                )

        # Use provided sources or default configuration sources
        search_sources = sources or self.sources

        # Try different lookup methods in priority order
        # Map source names to method names for filtering
        source_method_mapping = {
            "amazon": "amazon-search",
            "amazon-search": "amazon-search",
            "goodreads": "google-books",  # Goodreads data comes via Google Books API
            "google-books": "google-books",
            "openlibrary": "openlibrary",
        }

        # Define lookup methods with enhanced variation support (Issue #55)
        lookup_method_definitions = [
            ("amazon-search", self._lookup_via_amazon_search),
            (
                "google-books",
                lambda isbn, title, author, verbose: self._lookup_via_google_books(
                    isbn, title, author, verbose
                ),
            ),
            (
                "openlibrary",
                lambda isbn, title, author, verbose: self._lookup_via_openlibrary(
                    isbn, title, author, verbose
                ),
            ),
        ]

        # Track errors for better error reporting
        source_errors = {}
        methods_attempted = []

        # Enhanced lookup with title and author variations
        for method_name, method_func in lookup_method_definitions:
            # Skip if source not in requested sources using proper mapping
            method_should_run = False
            for requested_source in search_sources:
                mapped_method = source_method_mapping.get(
                    requested_source, requested_source
                )
                if mapped_method == method_name:
                    method_should_run = True
                    break

            if not method_should_run:
                continue

            methods_attempted.append(method_name)

            try:
                if progress_callback:
                    progress_callback(description=f"Trying {method_name}...")

                self.logger.info(f"Trying lookup method: {method_name}")
                if verbose:
                    self.logger.info(
                        f"ASIN lookup: Starting {method_name} for '{title}' by {author or 'unknown author'}"
                    )

                asin_found = None
                variation_used = None

                # Performance optimization: Try original title/author first, then variations
                title_author_combinations = []

                # Always try original combination first
                title_author_combinations.append((title, author))

                # Then add variations (skip if original already in list)
                for title_var in title_variations:
                    for author_var in author_variations:
                        combo = (title_var, author_var)
                        if combo not in title_author_combinations:
                            title_author_combinations.append(combo)

                # Try each title/author combination
                for title_var, author_var in title_author_combinations:
                    try:
                        # Log variation attempts (but not the original)
                        if verbose and (title_var != title or author_var != author):
                            self.logger.info(
                                f"ASIN lookup: Trying {method_name} variation - Title: '{title_var}', Author: '{author_var}'"
                            )

                        # Call the appropriate method based on method name
                        if method_name == "amazon-search":
                            asin_found = method_func(title_var, author_var, verbose)
                        else:
                            asin_found = method_func(
                                None, title_var, author_var, verbose
                            )

                        if asin_found and self.validate_asin(asin_found):
                            # Only mark as variation if it's not the original
                            if title_var != title or author_var != author:
                                variation_used = (
                                    f"Title: '{title_var}', Author: '{author_var}'"
                                )
                            break

                    except Exception as var_e:
                        if verbose:
                            self.logger.debug(
                                f"Variation failed for {method_name}: {var_e}"
                            )
                        continue

                    if asin_found:
                        break

                if asin_found and self.validate_asin(asin_found):
                    if variation_used and verbose:
                        self.logger.info(
                            f"ASIN found via {method_name} using variation: {variation_used}"
                        )
                    else:
                        self.logger.info(f"ASIN found via {method_name}: {asin_found}")

                    # Cache the result using original title/author key
                    if use_cache:
                        self.cache_manager.cache_asin(cache_key, asin_found)

                    return ASINLookupResult(
                        query_title=title,
                        query_author=author,
                        asin=asin_found,
                        metadata=(
                            {"variation_used": variation_used}
                            if variation_used
                            else None
                        ),
                        source=method_name,
                        success=True,
                        lookup_time=time.time() - start_time,
                        from_cache=False,
                    )
                else:
                    if verbose:
                        if asin_found:
                            self.logger.info(
                                f"ASIN lookup: {method_name} returned invalid ASIN: {asin_found}"
                            )
                        else:
                            self.logger.info(
                                f"ASIN lookup: {method_name} returned no results across {len(title_variations)} title variations"
                            )
                    source_errors[method_name] = (
                        f"No valid ASIN found across {len(title_variations)} title variations"
                    )

                # Rate limiting between attempts
                time.sleep(self.rate_limit)

            except Exception as e:
                error_msg = str(e)
                source_errors[method_name] = error_msg
                self.logger.warning(f"Lookup method {method_name} failed: {e}")
                if verbose:
                    self.logger.error(
                        f"ASIN lookup: Detailed error for {method_name}: {e}",
                        exc_info=True,
                    )
                continue

        # No ASIN found - create detailed error message
        if verbose:
            self.logger.info(
                f"ASIN lookup summary for '{title}' by {author or 'unknown author'}:"
            )
            self.logger.info(f"  Methods attempted: {methods_attempted}")
            for method, error in source_errors.items():
                self.logger.info(f"  {method}: {error}")

        # Create detailed error message
        if source_errors:
            error_details = "; ".join(
                [f"{method}: {error}" for method, error in source_errors.items()]
            )
            error_message = f"No ASIN found. Sources attempted: {error_details}"
        else:
            error_message = (
                f"No ASIN sources available for the requested sources: {search_sources}"
            )

        self.logger.info(f"No ASIN found for '{title}' by {author or 'unknown author'}")
        return ASINLookupResult(
            query_title=title,
            query_author=author,
            asin=None,
            metadata=source_errors,  # Pass source errors as metadata for debugging
            source=None,
            success=False,
            error=error_message,
            lookup_time=time.time() - start_time,
            from_cache=False,
        )

    def lookup_by_isbn(
        self,
        isbn: str,
        sources: Optional[List[str]] = None,
        use_cache: bool = True,
        progress_callback=None,
        verbose: bool = False,
    ) -> ASINLookupResult:
        """Look up ASIN by ISBN."""
        start_time = time.time()
        self.logger.info(f"Looking up ASIN for ISBN: {isbn}")

        if progress_callback:
            progress_callback(description="Starting ISBN lookup...")

        # Create cache key
        cache_key = f"isbn_{isbn}".lower()

        # Check cache first if enabled
        if use_cache:
            cached_asin = self.cache_manager.get_cached_asin(cache_key)
            if cached_asin:
                self.logger.info(f"Cache hit for ISBN: {isbn}")
                return ASINLookupResult(
                    query_title=f"ISBN:{isbn}",
                    query_author=None,
                    asin=cached_asin,
                    metadata=None,
                    source="cache",
                    success=True,
                    lookup_time=time.time() - start_time,
                    from_cache=True,
                )

        # Use provided sources or default configuration sources
        search_sources = sources or self.sources

        # Try different lookup methods in priority order for ISBN
        # Map source names to method names for filtering
        source_method_mapping = {
            "amazon": [
                "isbn-direct",
                "google-books-metadata",
            ],  # Try both Amazon methods
            "amazon-search": ["isbn-direct", "google-books-metadata"],
            "goodreads": [
                "google-books-direct",
                "google-books-metadata",
            ],  # Goodreads data comes via Google Books API
            "google-books": ["google-books-direct", "google-books-metadata"],
            "openlibrary": ["openlibrary"],
        }

        lookup_methods = [
            ("isbn-direct", lambda: self._lookup_by_isbn_direct(isbn)),
            (
                "google-books-direct",
                lambda: self._lookup_via_google_books(isbn, None, None, verbose),
            ),
            (
                "google-books-metadata",
                lambda: self._lookup_isbn_via_metadata_search(isbn, verbose),
            ),
            (
                "openlibrary",
                lambda: self._lookup_via_openlibrary(isbn, verbose=verbose),
            ),
        ]

        for method_name, method in lookup_methods:
            # Skip if source not in requested sources using proper mapping
            method_should_run = False
            for requested_source in search_sources:
                mapped_methods = source_method_mapping.get(
                    requested_source, [requested_source]
                )
                # Handle both list and single string mapping
                if isinstance(mapped_methods, str):
                    mapped_methods = [mapped_methods]
                if method_name in mapped_methods:
                    method_should_run = True
                    break

            if not method_should_run:
                continue

            try:
                if progress_callback:
                    progress_callback(description=f"Trying {method_name}...")

                self.logger.debug(f"Trying lookup method: {method_name}")
                asin = method()

                if asin and self.validate_asin(asin):
                    self.logger.info(f"ASIN found via {method_name}: {asin}")

                    # Cache the result
                    if use_cache:
                        self.cache_manager.cache_asin(cache_key, asin)

                    return ASINLookupResult(
                        query_title=f"ISBN:{isbn}",
                        query_author=None,
                        asin=asin,
                        metadata=None,
                        source=method_name,
                        success=True,
                        lookup_time=time.time() - start_time,
                        from_cache=False,
                    )

                # Rate limiting between attempts
                time.sleep(self.rate_limit)

            except Exception as e:
                self.logger.warning(f"Lookup method {method_name} failed: {e}")
                continue

        # No ASIN found
        self.logger.info(f"No ASIN found for ISBN: {isbn}")
        return ASINLookupResult(
            query_title=f"ISBN:{isbn}",
            query_author=None,
            asin=None,
            metadata=None,
            source=None,
            success=False,
            error="No ASIN found from any source",
            lookup_time=time.time() - start_time,
            from_cache=False,
        )

    def batch_update(
        self,
        books: List[Book],
        sources: Optional[List[str]] = None,
        parallel: int = 2,
        progress_callback=None,
    ) -> List[ASINLookupResult]:
        """Perform batch ASIN lookup for multiple books."""
        self.logger.info(f"Starting batch ASIN lookup for {len(books)} books")

        results = []

        def lookup_single_book(book: Book) -> ASINLookupResult:
            """Lookup ASIN for a single book."""
            try:
                # Prefer ISBN lookup if available, otherwise use title/author
                if book.isbn:
                    result = self.lookup_by_isbn(
                        book.isbn,
                        sources=sources,
                        use_cache=True,
                        progress_callback=None,  # No individual progress for batch
                    )
                else:
                    result = self.lookup_by_title(
                        book.title,
                        author=book.author,
                        sources=sources,
                        use_cache=True,
                        progress_callback=None,  # No individual progress for batch
                    )

                return result

            except Exception as e:
                self.logger.error(f"Failed to lookup ASIN for book '{book.title}': {e}")
                return ASINLookupResult(
                    query_title=book.title,
                    query_author=book.author,
                    asin=None,
                    metadata=None,
                    source=None,
                    success=False,
                    error=str(e),
                )

        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = []

            for i, book in enumerate(books):
                future = executor.submit(lookup_single_book, book)
                futures.append(future)

                # Update progress if callback provided
                if progress_callback:
                    progress_callback(
                        description=f"Submitted lookup {i + 1}/{len(books)}: {book.title}"
                    )

                # Stagger requests to respect rate limits
                time.sleep(self.rate_limit / parallel)

            # Collect results as they complete
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    result = future.result()
                    results.append(result)

                    if progress_callback:
                        progress_callback(
                            description=f"Completed lookup {len(results)}/{len(books)}"
                        )

                except Exception as e:
                    self.logger.error(f"Batch lookup failed for future {i}: {e}")
                    # Create a failed result
                    results.append(
                        ASINLookupResult(
                            query_title="Unknown",
                            query_author=None,
                            asin=None,
                            metadata=None,
                            source=None,
                            success=False,
                            error=str(e),
                        )
                    )

        successful_lookups = sum(1 for r in results if r.success)
        self.logger.info(
            f"Batch ASIN lookup completed: {successful_lookups}/{len(books)} successful"
        )

        return results

    def validate_asin(self, asin: str) -> bool:
        """Validate ASIN format - specifically for Amazon ASINs (not ISBNs)."""
        if not asin or not isinstance(asin, str):
            return False

        # Amazon ASINs for books start with 'B' and are exactly 10 characters
        # Pattern: B followed by 9 alphanumeric characters
        asin_pattern = re.compile(r"^B[A-Z0-9]{9}$")
        return bool(asin_pattern.match(asin.upper()))

    def check_availability(self, asin: str, progress_callback=None):
        """Check if ASIN is available on Amazon."""
        self.logger.info(f"Checking availability for ASIN: {asin}")

        if progress_callback:
            progress_callback(description=f"Checking availability for {asin}...")

        try:
            # Simple availability check by accessing Amazon product page
            url = f"https://www.amazon.com/dp/{asin}"
            headers = {"User-Agent": self.user_agents[0]}

            response = requests.get(
                url, headers=headers, timeout=10, allow_redirects=True
            )

            # Check if we got a valid product page
            if response.status_code == 200:
                # Look for signs that the product exists and is available
                content = response.text.lower()

                # Basic availability indicators
                if "currently unavailable" in content or "page not found" in content:
                    available = False
                    metadata = {"status": "unavailable"}
                else:
                    available = True
                    metadata = {"status": "available", "url": response.url}
            else:
                available = False
                metadata = {"status": "not_found", "status_code": response.status_code}

        except Exception as e:
            self.logger.error(f"Availability check failed for {asin}: {e}")
            available = False
            metadata = {"status": "error", "error": str(e)}

        from dataclasses import dataclass

        @dataclass
        class Availability:
            available: bool = False
            metadata: Optional[Dict[str, Any]] = None

        return Availability(available=available, metadata=metadata)

    def _lookup_by_isbn_direct(self, isbn: str) -> Optional[str]:
        """Direct ISBN to ASIN lookup via Amazon redirect with enhanced Kindle edition detection."""
        if not isbn:
            return None

        # Clean ISBN
        clean_isbn = re.sub(r"[^0-9X]", "", isbn.upper())

        try:
            # Try Amazon ISBN redirect
            url = f"https://www.amazon.com/dp/{clean_isbn}"
            headers = {"User-Agent": self.user_agents[0]}

            response = requests.get(
                url, headers=headers, allow_redirects=True, timeout=10
            )

            if response.status_code == 200:
                # Look for ASIN in the final URL (direct redirect)
                final_url = response.url
                asin_match = re.search(r"/dp/([B][A-Z0-9]{9})", final_url)

                if asin_match:
                    self.logger.debug(
                        f"ISBN direct lookup: Found ASIN via redirect: {asin_match.group(1)}"
                    )
                    return asin_match.group(1)

                # If no redirect to ASIN, parse the page content for Kindle editions
                self.logger.debug(
                    "ISBN direct lookup: No ASIN redirect, parsing page content"
                )
                soup = BeautifulSoup(response.content, "html.parser")

                # Strategy 1: Look for Kindle edition links in format switcher or related products
                format_links = soup.find_all("a", href=True)

                for link in format_links:
                    href = link.get("href", "")

                    # Look for links that mention kindle, ebook, or digital
                    link_text = link.get_text(strip=True).lower()
                    if (
                        "kindle" in href.lower()
                        or "kindle" in link_text
                        or "ebook" in href.lower()
                        or "ebook" in link_text
                        or "digital" in link_text
                    ):

                        # Extract ASIN from these links
                        asin_match = re.search(r"/dp/([B][A-Z0-9]{9})", href)
                        if asin_match:
                            asin = asin_match.group(1)
                            self.logger.debug(
                                f"ISBN direct lookup: Found Kindle ASIN: {asin}"
                            )
                            return asin

                # Strategy 2: Look for ASINs in JavaScript or hidden data
                scripts = soup.find_all("script", string=True)

                for script in scripts[:10]:  # Check first 10 scripts
                    script_content = script.string
                    if script_content and "kindle" in script_content.lower():
                        # Look for ASIN patterns in Kindle-related JavaScript
                        asin_matches = re.findall(r"([B][A-Z0-9]{9})", script_content)
                        for asin_candidate in asin_matches:
                            if self.validate_asin(asin_candidate):
                                self.logger.debug(
                                    f"ISBN direct lookup: Found ASIN in Kindle script: {asin_candidate}"
                                )
                                return asin_candidate

                # Strategy 3: Look in the page source for common Kindle ASIN patterns
                page_content = response.text

                # Look for data attributes that might contain Kindle ASINs
                asin_patterns = [
                    r'data-asin["\']?\s*[=:]\s*["\']([B][A-Z0-9]{9})["\']',  # data-asin attributes
                    r'"asin"\s*:\s*"([B][A-Z0-9]{9})"',  # JSON asin fields
                    r'asin["\']?\s*[=:]\s*["\']([B][A-Z0-9]{9})["\']',  # asin variables
                ]

                for pattern in asin_patterns:
                    matches = re.findall(pattern, page_content, re.IGNORECASE)
                    for match in matches:
                        if self.validate_asin(match):
                            self.logger.debug(
                                f"ISBN direct lookup: Found ASIN via pattern match: {match}"
                            )
                            return match

                self.logger.debug("ISBN direct lookup: No Kindle ASINs found on page")

        except Exception as e:
            self.logger.debug(f"ISBN direct lookup failed: {e}")

        return None

    def _lookup_isbn_via_metadata_search(
        self, isbn: str, verbose: bool = False
    ) -> Optional[str]:
        """ISBN lookup using Google Books metadata to get title/author, then Amazon search for ASIN."""
        if not isbn:
            return None

        try:
            # Step 1: Get book metadata from Google Books
            if verbose:
                self.logger.info(f"ISBN metadata search: Getting metadata for {isbn}")

            result = self._lookup_via_google_books(
                isbn, None, None, verbose, return_metadata=True
            )

            if not result or len(result) != 2:
                self.logger.debug(
                    f"ISBN metadata search: No metadata returned for {isbn}"
                )
                return None

            asin, metadata = result

            # If Google Books already found an ASIN, return it
            if asin:
                self.logger.debug(
                    f"ISBN metadata search: ASIN found directly from Google Books: {asin}"
                )
                return asin

            # Extract title and author from metadata
            if not metadata:
                self.logger.debug(
                    f"ISBN metadata search: No metadata available for {isbn}"
                )
                return None

            title = metadata.get("title")
            authors = metadata.get("authors", [])
            author = authors[0] if authors else None

            if not title:
                self.logger.debug(
                    f"ISBN metadata search: No title found in metadata for {isbn}"
                )
                return None

            if verbose:
                self.logger.info(
                    f"ISBN metadata search: Found metadata - Title: '{title}', Author: '{author}'"
                )

            # Step 2: Use title/author to search Amazon for the Kindle ASIN
            self.logger.debug(
                f"ISBN metadata search: Searching Amazon for Kindle edition of '{title}' by {author}"
            )

            asin = self._lookup_via_amazon_search(title, author, verbose)

            if asin:
                if verbose:
                    self.logger.info(
                        f"ISBN metadata search: Found Kindle ASIN via Amazon search: {asin}"
                    )
                return asin
            else:
                self.logger.debug(
                    f"ISBN metadata search: No ASIN found via Amazon search for '{title}' by {author}"
                )

        except Exception as e:
            self.logger.debug(f"ISBN metadata search failed for {isbn}: {e}")
            if verbose:
                self.logger.error(
                    f"ISBN metadata search detailed error: {e}", exc_info=True
                )

        return None

    def _lookup_via_amazon_search(
        self, title: str, author: Optional[str], verbose: bool = False
    ) -> Optional[str]:
        """Web scraping of Amazon search results with retry logic and multiple strategies."""
        if not title:
            self.logger.debug("Amazon search: No title provided")
            return None

        # Multiple search strategies to try
        search_strategies = [
            # Strategy 1: Books section search
            {"i": "stripbooks", "section": "books"},
            # Strategy 2: Kindle eBooks section
            {"i": "digital-text", "section": "kindle"},
            # Strategy 3: All departments
            {"section": "all-departments"},
        ]

        for strategy_idx, strategy in enumerate(search_strategies):
            try:
                # Create search query
                query = title
                if author:
                    query = f"{title} {author}"

                # URL encode the query properly
                import urllib.parse

                query_encoded = urllib.parse.quote_plus(query)

                # Build URL based on strategy
                if "i" in strategy:
                    url = (
                        f"https://www.amazon.com/s?k={query_encoded}&i={strategy['i']}"
                    )
                else:
                    url = f"https://www.amazon.com/s?k={query_encoded}"

                if verbose:
                    self.logger.info(
                        f"Amazon search: Strategy {strategy_idx + 1} ({strategy['section']}) for '{query}' -> URL: {url}"
                    )
                else:
                    self.logger.debug(
                        f"Amazon search: Strategy {strategy_idx + 1} for '{query}'"
                    )

                # Try with different user agents and retry logic
                for attempt in range(3):  # 3 attempts per strategy
                    try:
                        # Rotate user agents
                        user_agent = self.user_agents[attempt % len(self.user_agents)]
                        headers = {
                            "User-Agent": user_agent,
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                            "Accept-Encoding": "gzip, deflate",
                            "DNT": "1",
                            "Connection": "keep-alive",
                            "Upgrade-Insecure-Requests": "1",
                        }

                        if verbose and attempt == 0:
                            self.logger.info(
                                f"Amazon search: Using User-Agent: {user_agent[:60]}..."
                            )

                        response = requests.get(url, headers=headers, timeout=15)

                        self.logger.debug(
                            f"Amazon search: Attempt {attempt + 1}, status: {response.status_code}, content length: {len(response.content)} bytes"
                        )

                        if verbose and attempt == 0:
                            response_headers = dict(response.headers)
                            # Remove sensitive headers for logging
                            safe_headers = {
                                k: v
                                for k, v in response_headers.items()
                                if k.lower() not in ["set-cookie"]
                            }
                            self.logger.info(
                                f"Amazon search: Response headers: {safe_headers}"
                            )

                        if response.status_code == 200:
                            soup = BeautifulSoup(response.content, "html.parser")

                            # Multiple selector strategies for finding ASINs
                            asin_found = self._extract_asin_from_amazon_page(
                                soup, verbose, strategy["section"]
                            )
                            if asin_found:
                                return asin_found

                        elif response.status_code == 503:
                            self.logger.debug(
                                "Amazon search: Service unavailable (503), retrying with different user agent"
                            )
                            time.sleep(2**attempt)  # Exponential backoff
                            continue
                        elif response.status_code == 429:
                            self.logger.debug(
                                "Amazon search: Rate limited (429), backing off"
                            )
                            time.sleep(
                                5 * (attempt + 1)
                            )  # Linear backoff for rate limiting
                            continue
                        else:
                            self.logger.warning(
                                f"Amazon search: HTTP {response.status_code} response"
                            )
                            if verbose:
                                self.logger.info(
                                    f"Amazon search: Response content preview: {response.text[:500]}"
                                )
                            break  # Don't retry for other HTTP errors

                    except requests.exceptions.Timeout:
                        self.logger.debug(
                            f"Amazon search: Timeout on attempt {attempt + 1}"
                        )
                        if attempt < 2:  # Don't sleep on last attempt
                            time.sleep(1)
                        continue
                    except requests.exceptions.ConnectionError as e:
                        self.logger.debug(
                            f"Amazon search: Connection error on attempt {attempt + 1}: {e}"
                        )
                        if attempt < 2:
                            time.sleep(2)
                        continue

                # Small delay between strategies to be respectful
                time.sleep(1)

            except Exception as e:
                self.logger.debug(
                    f"Amazon search strategy {strategy_idx + 1} failed: {e}"
                )
                if verbose:
                    self.logger.error(
                        f"Amazon search detailed error for strategy {strategy_idx + 1}: {e}",
                        exc_info=True,
                    )
                continue

        self.logger.debug("Amazon search: No ASIN found with any strategy")
        return None

    def _extract_asin_from_amazon_page(
        self, soup: BeautifulSoup, verbose: bool, section: str
    ) -> Optional[str]:
        """Extract ASIN from Amazon search page using multiple selector strategies."""

        # Strategy 1: data-asin attributes (most common)
        products = soup.find_all(attrs={"data-asin": True})
        self.logger.debug(
            f"Amazon search ({section}): Found {len(products)} products with data-asin attribute"
        )

        # Log some sample ASINs found for debugging
        sample_asins = []
        for product in products[:5]:  # Check first 5 for debugging
            asin = product.get("data-asin")
            if asin:
                sample_asins.append(asin)

        if verbose and sample_asins:
            self.logger.info(
                f"Amazon search ({section}): Sample ASINs found: {sample_asins}"
            )

        # Look for valid book ASINs (start with 'B' and are 10 chars)
        for product in products:
            asin = product.get("data-asin")
            if asin and asin.startswith("B") and len(asin) == 10:
                self.logger.debug(
                    f"Amazon search ({section}): Found valid ASIN: {asin}"
                )
                return asin

        # Strategy 2: ASINs in href attributes of links
        self.logger.debug(
            f"Amazon search ({section}): No valid ASINs in data-asin, trying href links"
        )
        asin_links = soup.find_all("a", href=True)

        for link in asin_links[:30]:  # Check first 30 links
            href = link.get("href", "")
            # Look for patterns like /dp/B123456789, /gp/product/B123456789, etc.
            asin_patterns = [
                r"/dp/([B][A-Z0-9]{9})",
                r"/gp/product/([B][A-Z0-9]{9})",
                r"ASIN=([B][A-Z0-9]{9})",
                r"asin=([B][A-Z0-9]{9})",
            ]

            for pattern in asin_patterns:
                asin_match = re.search(pattern, href)
                if asin_match:
                    asin = asin_match.group(1)
                    self.logger.debug(
                        f"Amazon search ({section}): Found ASIN in link: {asin} (pattern: {pattern})"
                    )
                    return asin

        # Strategy 3: Look in JavaScript/JSON data on page
        self.logger.debug(
            f"Amazon search ({section}): Trying to extract from page scripts"
        )
        scripts = soup.find_all("script", string=True)

        for script in scripts[:10]:  # Check first 10 scripts
            script_content = script.string
            if script_content and "asin" in script_content.lower():
                # Look for ASIN patterns in JavaScript
                asin_matches = re.findall(
                    r'"asin"\s*:\s*"([B][A-Z0-9]{9})"', script_content, re.IGNORECASE
                )
                if asin_matches:
                    asin = asin_matches[0]
                    self.logger.debug(
                        f"Amazon search ({section}): Found ASIN in script: {asin}"
                    )
                    return asin

                # Alternative JS pattern
                asin_matches = re.findall(r'["\']([B][A-Z0-9]{9})["\']', script_content)
                if asin_matches:
                    asin = asin_matches[0]
                    self.logger.debug(
                        f"Amazon search ({section}): Found ASIN candidate in script: {asin}"
                    )
                    return asin

        # Strategy 4: Check meta tags or other elements
        self.logger.debug(
            f"Amazon search ({section}): Trying meta tags and other elements"
        )

        # Check for ASINs in various element attributes
        elements_with_ids = soup.find_all(
            attrs={"id": re.compile(r".*[Bb][A-Z0-9]{9}.*")}
        )
        for elem in elements_with_ids:
            elem_id = elem.get("id", "")
            asin_match = re.search(r"([B][A-Z0-9]{9})", elem_id)
            if asin_match:
                asin = asin_match.group(1)
                self.logger.debug(
                    f"Amazon search ({section}): Found ASIN in element ID: {asin}"
                )
                return asin

        self.logger.debug(
            f"Amazon search ({section}): No ASIN found with any extraction method"
        )
        return None

    def _lookup_via_google_books(
        self,
        isbn: Optional[str],
        title: Optional[str],
        author: Optional[str],
        verbose: bool = False,
        return_metadata: bool = False,
    ) -> Optional[str]:
        """Google Books API lookup with improved query formatting and multiple strategies.

        Args:
            isbn: ISBN to search for
            title: Title to search for
            author: Author to search for
            verbose: Enable verbose logging
            return_metadata: If True, return (asin, metadata) tuple instead of just asin

        Returns:
            ASIN string or None (or tuple if return_metadata=True)
        """

        # Multiple query strategies to improve success rate
        strategies = []

        if isbn:
            strategies.append(("isbn", f"isbn:{isbn}"))

        if title and author:
            # Strategy 1: Exact title and author search
            strategies.append(
                ("title_author_exact", f'intitle:"{title}"+inauthor:"{author}"')
            )
            # Strategy 2: Title and author without quotes (broader search)
            strategies.append(
                ("title_author_broad", f"intitle:{title}+inauthor:{author}")
            )
            # Strategy 3: Combined search without field specifiers
            strategies.append(("combined", f'"{title} {author}"'))
            # Strategy 4: Title only with author as general query
            strategies.append(("title_focused", f'intitle:"{title}"+{author}'))
        elif title:
            # Strategy 5: Title only searches
            strategies.append(("title_exact", f'intitle:"{title}"'))
            strategies.append(("title_broad", f"{title}"))
        elif author:
            # Strategy 6: Author only search
            strategies.append(("author_only", f'inauthor:"{author}"'))

        if not strategies:
            self.logger.debug("Google Books: No query parameters provided")
            return None if not return_metadata else (None, None)

        for strategy_name, query in strategies:
            try:
                # URL encode the query properly
                import urllib.parse

                encoded_query = urllib.parse.quote(query)
                url = f"https://www.googleapis.com/books/v1/volumes?q={encoded_query}&maxResults=10"

                if verbose:
                    self.logger.info(
                        f"Google Books: Strategy '{strategy_name}' -> Query: {query}"
                    )
                    self.logger.info(f"Google Books: URL: {url}")
                else:
                    self.logger.debug(
                        f"Google Books: Strategy '{strategy_name}' with query: {query}"
                    )

                # Add retry logic with backoff
                for attempt in range(3):
                    try:
                        headers = {
                            "User-Agent": self.user_agents[
                                attempt % len(self.user_agents)
                            ],
                            "Accept": "application/json",
                        }

                        response = requests.get(url, headers=headers, timeout=15)

                        self.logger.debug(
                            f"Google Books ({strategy_name}): Attempt {attempt + 1}, status: {response.status_code}, content length: {len(response.content)} bytes"
                        )

                        if response.status_code == 200:
                            data = response.json()

                            total_items = data.get("totalItems", 0)
                            items = data.get("items", [])

                            self.logger.debug(
                                f"Google Books ({strategy_name}): Found {total_items} total items, {len(items)} returned"
                            )

                            if verbose and items:
                                # Log details of first few results
                                for i, item in enumerate(items[:3]):
                                    volume_info = item.get("volumeInfo", {})
                                    title_found = volume_info.get("title", "Unknown")
                                    authors_found = volume_info.get(
                                        "authors", ["Unknown"]
                                    )
                                    published_date = volume_info.get(
                                        "publishedDate", "Unknown"
                                    )
                                    self.logger.info(
                                        f"Google Books ({strategy_name}): Result {i + 1}: '{title_found}' by {authors_found} ({published_date})"
                                    )

                            # Try different ASIN extraction methods
                            asin_found = self._extract_asin_from_google_books_result(
                                data, verbose, strategy_name
                            )
                            if asin_found:
                                if return_metadata:
                                    return (asin_found, data)
                                return asin_found

                            # If we're doing ISBN lookup and no ASIN found, but we got book metadata,
                            # return the metadata so we can do a title/author lookup
                            if return_metadata and isbn and items:
                                # Return the first valid book result for secondary lookup
                                for item in items:
                                    volume_info = item.get("volumeInfo", {})
                                    if volume_info.get("title") and volume_info.get(
                                        "authors"
                                    ):
                                        return (None, volume_info)

                            break  # Success, no need to retry this strategy

                        elif response.status_code == 429:
                            self.logger.debug(
                                f"Google Books ({strategy_name}): Rate limited (429), backing off"
                            )
                            time.sleep(2**attempt)  # Exponential backoff
                            continue
                        elif response.status_code >= 500:
                            self.logger.debug(
                                f"Google Books ({strategy_name}): Server error ({response.status_code}), retrying"
                            )
                            time.sleep(1 + attempt)
                            continue
                        else:
                            self.logger.warning(
                                f"Google Books ({strategy_name}): HTTP {response.status_code} response"
                            )
                            if verbose:
                                self.logger.info(
                                    f"Google Books ({strategy_name}): Response content: {response.text[:500]}"
                                )
                            break  # Don't retry for client errors

                    except requests.exceptions.Timeout:
                        self.logger.debug(
                            f"Google Books ({strategy_name}): Timeout on attempt {attempt + 1}"
                        )
                        if attempt < 2:
                            time.sleep(1)
                        continue
                    except requests.exceptions.RequestException as e:
                        self.logger.debug(
                            f"Google Books ({strategy_name}): Request error on attempt {attempt + 1}: {e}"
                        )
                        if attempt < 2:
                            time.sleep(1)
                        continue

                # Small delay between strategies
                time.sleep(0.5)

            except Exception as e:
                self.logger.debug(
                    f"Google Books strategy '{strategy_name}' failed: {e}"
                )
                if verbose:
                    self.logger.error(
                        f"Google Books detailed error for strategy '{strategy_name}': {e}",
                        exc_info=True,
                    )
                continue

        self.logger.debug("Google Books: No ASIN found with any strategy")
        return None if not return_metadata else (None, None)

    def _extract_asin_from_google_books_result(
        self, data: dict, verbose: bool, strategy_name: str
    ) -> Optional[str]:
        """Extract ASIN from Google Books API response using multiple methods."""

        items = data.get("items", [])
        if not items:
            return None

        # Method 1: Look for ASIN in industryIdentifiers
        for item in items:
            volume_info = item.get("volumeInfo", {})
            industry_identifiers = volume_info.get("industryIdentifiers", [])

            if verbose:
                self.logger.info(
                    f"Google Books ({strategy_name}): Checking identifiers: {industry_identifiers}"
                )

            for identifier in industry_identifiers:
                identifier_type = identifier.get("type")
                identifier_value = identifier.get("identifier", "")

                self.logger.debug(
                    f"Google Books ({strategy_name}): Found identifier type '{identifier_type}': {identifier_value}"
                )

                # Check for ASIN in 'OTHER' type identifiers
                if identifier_type == "OTHER" and self.validate_asin(identifier_value):
                    self.logger.debug(
                        f"Google Books ({strategy_name}): Found valid ASIN in identifiers: {identifier_value}"
                    )
                    return identifier_value

                # Sometimes ASINs are listed as ISBN_13 or other types
                if self.validate_asin(identifier_value):
                    self.logger.debug(
                        f"Google Books ({strategy_name}): Found valid ASIN in '{identifier_type}' identifier: {identifier_value}"
                    )
                    return identifier_value

        # Method 2: Extract from various link fields
        for item in items:
            volume_info = item.get("volumeInfo", {})

            # Check multiple link fields for Amazon URLs
            link_fields = ["infoLink", "canonicalVolumeLink", "previewLink"]
            for link_key in link_fields:
                link = volume_info.get(link_key, "")
                if link and "amazon" in link.lower():
                    self.logger.debug(
                        f"Google Books ({strategy_name}): Found Amazon link in '{link_key}': {link}"
                    )

                    # Multiple ASIN extraction patterns
                    asin_patterns = [
                        r"[/?]dp/([B][A-Z0-9]{9})",
                        r"[/?]([B][A-Z0-9]{9})",
                        r"ASIN=([B][A-Z0-9]{9})",
                        r"asin=([B][A-Z0-9]{9})",
                    ]

                    for pattern in asin_patterns:
                        asin_match = re.search(pattern, link, re.IGNORECASE)
                        if asin_match:
                            asin = asin_match.group(1)
                            self.logger.debug(
                                f"Google Books ({strategy_name}): Extracted ASIN from {link_key}: {asin}"
                            )
                            return asin

        # Method 3: Look for ASINs in the raw JSON response (sometimes hidden in other fields)
        json_str = json.dumps(data)
        asin_matches = re.findall(r"([B][A-Z0-9]{9})", json_str)

        for asin_candidate in asin_matches:
            if self.validate_asin(asin_candidate):
                self.logger.debug(
                    f"Google Books ({strategy_name}): Found ASIN in raw JSON: {asin_candidate}"
                )
                return asin_candidate

        # Method 4: Check for ISBN that might be an ASIN (sometimes mislabeled)
        for item in items:
            volume_info = item.get("volumeInfo", {})
            industry_identifiers = volume_info.get("industryIdentifiers", [])

            for identifier in industry_identifiers:
                identifier_value = identifier.get("identifier", "")
                # Check if any "ISBN" is actually an ASIN
                if len(identifier_value) == 10 and identifier_value.startswith("B"):
                    if self.validate_asin(identifier_value):
                        self.logger.debug(
                            f"Google Books ({strategy_name}): Found ASIN mislabeled as ISBN: {identifier_value}"
                        )
                        return identifier_value

        self.logger.debug(f"Google Books ({strategy_name}): No ASIN found in results")
        return None

    def _lookup_via_openlibrary(
        self,
        isbn: Optional[str],
        title: Optional[str] = None,
        author: Optional[str] = None,
        verbose: bool = False,
    ) -> Optional[str]:
        """OpenLibrary API lookup."""
        try:
            # Try ISBN lookup first if available
            if isbn:
                clean_isbn = re.sub(r"[^0-9X]", "", isbn.upper())
                url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"

                if verbose:
                    self.logger.info(
                        f"OpenLibrary: ISBN lookup for {clean_isbn} -> URL: {url}"
                    )
                else:
                    self.logger.debug(f"OpenLibrary: ISBN lookup for {clean_isbn}")

                response = requests.get(url, timeout=10)

                self.logger.debug(
                    f"OpenLibrary: ISBN response status: {response.status_code}"
                )

                if response.status_code == 200:
                    data = response.json()

                    if verbose:
                        self.logger.info(
                            f"OpenLibrary: ISBN response data keys: {list(data.keys())}"
                        )

                    # OpenLibrary rarely has ASINs, but check identifiers
                    for book_data in data.values():
                        identifiers = book_data.get("identifiers", {})

                        if verbose:
                            self.logger.info(
                                f"OpenLibrary: Found identifiers: {list(identifiers.keys())}"
                            )

                        # Look for Amazon identifiers
                        amazon_ids = identifiers.get("amazon", [])
                        for amazon_id in amazon_ids:
                            if self.validate_asin(amazon_id):
                                self.logger.debug(
                                    f"OpenLibrary: Found valid ASIN: {amazon_id}"
                                )
                                return amazon_id

            # If no ISBN or ISBN lookup failed, try title/author search
            if title:
                # Build search query for OpenLibrary Search API
                search_params = []
                if title:
                    search_params.append(f"title:{title}")
                if author:
                    search_params.append(f"author:{author}")

                search_query = " AND ".join(search_params)
                # URL encode the search query
                import urllib.parse

                encoded_query = urllib.parse.quote(search_query)
                search_url = (
                    f"https://openlibrary.org/search.json?q={encoded_query}&limit=5"
                )

                if verbose:
                    self.logger.info(
                        f"OpenLibrary: Title/author search: '{search_query}' -> URL: {search_url}"
                    )
                else:
                    self.logger.debug(
                        f"OpenLibrary: Title/author search for '{search_query}'"
                    )

                search_response = requests.get(search_url, timeout=10)

                self.logger.debug(
                    f"OpenLibrary: Search response status: {search_response.status_code}"
                )

                if search_response.status_code == 200:
                    search_data = search_response.json()

                    num_found = search_data.get("numFound", 0)
                    docs = search_data.get("docs", [])

                    self.logger.debug(
                        f"OpenLibrary: Found {num_found} total results, {len(docs)} returned"
                    )

                    if verbose and docs:
                        # Log details of first few results
                        for i, doc in enumerate(docs[:3]):
                            doc_title = doc.get("title", "Unknown")
                            doc_author = doc.get("author_name", ["Unknown"])
                            self.logger.info(
                                f"OpenLibrary: Search result {i + 1}: '{doc_title}' by {doc_author}"
                            )

                    # Look through results for ISBNs that we can then lookup
                    for doc in docs:
                        # Check if this doc has ISBN
                        isbns = doc.get("isbn", [])
                        for isbn_candidate in isbns[:3]:  # Check first 3 ISBNs
                            if verbose:
                                self.logger.info(
                                    f"OpenLibrary: Trying ISBN from search result: {isbn_candidate}"
                                )

                            # Recursively lookup this ISBN
                            asin = self._lookup_via_openlibrary(
                                isbn_candidate, verbose=verbose
                            )
                            if asin:
                                return asin

        except Exception as e:
            self.logger.debug(f"OpenLibrary lookup failed: {e}")
            if verbose:
                self.logger.error(f"OpenLibrary detailed error: {e}", exc_info=True)

        self.logger.debug("OpenLibrary: No ASIN found")
        return None
