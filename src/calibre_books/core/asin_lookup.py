"""
ASIN lookup service for Calibre Books CLI.

This module provides functionality for looking up Amazon ASINs
from various sources including Amazon, Goodreads, and OpenLibrary.

Integrates the enhanced_asin_lookup.py functionality into the new CLI architecture.
"""

import requests
import time
import re
import json
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Tuple
import concurrent.futures
from bs4 import BeautifulSoup

from ..utils.logging import LoggerMixin
from .book import Book, ASINLookupResult
from .cache import create_cache_manager
from .rate_limiter import DomainRateLimiter, RateLimitedSession, RateLimitConfig

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
            cache_config = asin_config.get("cache", {})

            # Determine cache backend and path
            cache_backend = cache_config.get("backend", "sqlite")
            if cache_backend == "sqlite":
                self.cache_path = Path(
                    cache_config.get("path", "~/.book-tool/asin_cache.db")
                ).expanduser()
            else:
                self.cache_path = Path(
                    cache_config.get("path", "~/.book-tool/asin_cache.json")
                ).expanduser()

            self.sources = asin_config.get(
                "sources", ["amazon", "goodreads", "openlibrary"]
            )
            self.rate_limit = asin_config.get("rate_limit", 2.0)

            # Cache configuration
            self.cache_ttl_days = cache_config.get("ttl_days", 30)
            self.cache_backend = cache_backend
            self.auto_cleanup = cache_config.get("auto_cleanup", True)

            # Rate limiting configuration
            performance_config = asin_config.get("performance", {})
            self.max_parallel = performance_config.get("max_parallel", 4)
            self.connection_pool_size = performance_config.get(
                "connection_pool_size", 10
            )

            # Per-domain rate limits
            rate_limits = performance_config.get("rate_limits", {})

            self.logger.debug(
                f"Initialized ASIN lookup with sources: {self.sources}, cache: {self.cache_path} ({cache_backend})"
            )
        except Exception as e:
            self.logger.warning(f"Failed to load ASIN config, using defaults: {e}")
            self.cache_path = Path("~/.book-tool/asin_cache.db").expanduser()
            self.sources = ["amazon", "goodreads", "openlibrary"]
            self.rate_limit = 2.0
            self.cache_ttl_days = 30
            self.cache_backend = "sqlite"
            self.auto_cleanup = True
            self.max_parallel = 4
            self.connection_pool_size = 10
            rate_limits = {}

        self.logger.info(
            f"Initialized ASIN lookup service with sources: {self.sources}, cache backend: {self.cache_backend}"
        )

        # Initialize cache manager with new architecture
        self.cache_manager = create_cache_manager(
            self.cache_path,
            backend=self.cache_backend,
            ttl_days=self.cache_ttl_days,
            auto_cleanup=self.auto_cleanup,
        )

        # Initialize rate limiter with custom configurations
        custom_rate_configs = {}
        for domain, limit_config in rate_limits.items():
            if isinstance(limit_config, (int, float)):
                # Simple rate limit number
                custom_rate_configs[domain] = RateLimitConfig(
                    requests_per_second=float(limit_config)
                )
            elif isinstance(limit_config, dict):
                # Detailed configuration
                custom_rate_configs[domain] = RateLimitConfig(**limit_config)

        self.rate_limiter = DomainRateLimiter(custom_rate_configs)

        # Create rate-limited session for HTTP requests
        self.http_session = RateLimitedSession(
            self.rate_limiter,
            pool_connections=self.connection_pool_size,
            pool_maxsize=self.connection_pool_size * 2,
        )

        # User agents for web scraping - updated for 2025
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        ]

        # Thread lock for cache operations (still needed for some operations)
        self._cache_lock = threading.Lock()

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

        # Create cache key
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

        lookup_methods = [
            (
                "amazon-search",
                lambda: self._lookup_via_amazon_search(title, author, verbose),
            ),
            (
                "google-books",
                lambda: self._lookup_via_google_books(None, title, author, verbose),
            ),
            (
                "openlibrary",
                lambda: self._lookup_via_openlibrary(None, title, author, verbose),
            ),
        ]

        # Track errors for better error reporting
        source_errors = {}
        methods_attempted = []
        best_result = None

        for method_name, method in lookup_methods:
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

                asin = method()

                if asin and self.validate_asin(asin):
                    self.logger.info(f"ASIN found via {method_name}: {asin}")

                    # Calculate confidence score for this result
                    confidence = self.calculate_result_confidence(
                        asin, method_name, title, author
                    )

                    # Cache the result with source and confidence information
                    if use_cache:
                        self.cache_manager.cache_asin(
                            cache_key,
                            asin,
                            source=method_name,
                            confidence_score=confidence,
                        )

                    current_result = ASINLookupResult(
                        query_title=title,
                        query_author=author,
                        asin=asin,
                        metadata={"confidence": confidence},
                        source=method_name,
                        success=True,
                        lookup_time=time.time() - start_time,
                        from_cache=False,
                    )

                    # Check if this is good enough or if we should try more sources
                    if not self.should_try_more_sources(current_result):
                        self.logger.info(
                            f"High confidence result (score: {confidence:.2f}), stopping early"
                        )
                        return current_result

                    # Keep this as best result but continue searching for better
                    if not best_result or confidence > best_result.metadata.get(
                        "confidence", 0
                    ):
                        best_result = current_result
                else:
                    if verbose:
                        if asin:
                            self.logger.info(
                                f"ASIN lookup: {method_name} returned invalid ASIN: {asin}"
                            )
                        else:
                            self.logger.info(
                                f"ASIN lookup: {method_name} returned no results"
                            )
                    source_errors[method_name] = "No valid ASIN found"

                # Rate limiting is now handled by the RateLimitedSession automatically

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

        # Return best result if we found any
        if best_result:
            self.logger.info(
                f"Returning best result with confidence {best_result.metadata.get('confidence', 0):.2f}"
            )
            return best_result

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
            "amazon": "isbn-direct",
            "amazon-search": "isbn-direct",
            "goodreads": "google-books",  # Goodreads data comes via Google Books API
            "google-books": "google-books",
            "openlibrary": "openlibrary",
        }

        lookup_methods = [
            ("isbn-direct", lambda: self._lookup_by_isbn_direct(isbn)),
            (
                "google-books",
                lambda: self._lookup_via_google_books(isbn, None, None, verbose),
            ),
            (
                "openlibrary",
                lambda: self._lookup_via_openlibrary(isbn, verbose=verbose),
            ),
        ]

        best_result = None

        for method_name, method in lookup_methods:
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

            try:
                if progress_callback:
                    progress_callback(description=f"Trying {method_name}...")

                self.logger.debug(f"Trying lookup method: {method_name}")
                asin = method()

                if asin and self.validate_asin(asin):
                    self.logger.info(f"ASIN found via {method_name}: {asin}")

                    # Calculate confidence score for this result
                    confidence = self.calculate_result_confidence(
                        asin, method_name, f"ISBN:{isbn}", None, isbn
                    )

                    # Cache the result with source and confidence information
                    if use_cache:
                        self.cache_manager.cache_asin(
                            cache_key,
                            asin,
                            source=method_name,
                            confidence_score=confidence,
                        )

                    current_result = ASINLookupResult(
                        query_title=f"ISBN:{isbn}",
                        query_author=None,
                        asin=asin,
                        metadata={"confidence": confidence},
                        source=method_name,
                        success=True,
                        lookup_time=time.time() - start_time,
                        from_cache=False,
                    )

                    # Check if this is good enough or if we should try more sources
                    if not self.should_try_more_sources(current_result):
                        self.logger.info(
                            f"High confidence ISBN result (score: {confidence:.2f}), stopping early"
                        )
                        return current_result

                    # Keep this as best result but continue searching for better
                    if not best_result or confidence > best_result.metadata.get(
                        "confidence", 0
                    ):
                        best_result = current_result

                # Rate limiting is now handled by the RateLimitedSession automatically

            except Exception as e:
                self.logger.warning(f"Lookup method {method_name} failed: {e}")
                continue

        # Return best result if we found any
        if best_result:
            self.logger.info(
                f"Returning best ISBN result with confidence {best_result.metadata.get('confidence', 0):.2f}"
            )
            return best_result

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
        parallel: Optional[int] = None,
        progress_callback=None,
        sort_by_cache_likelihood: bool = True,
    ) -> List[ASINLookupResult]:
        """
        Perform intelligent batch ASIN lookup for multiple books.

        Args:
            books: List of books to lookup ASINs for
            sources: Sources to use for lookup
            parallel: Number of parallel workers (defaults to configured max_parallel)
            progress_callback: Progress callback function
            sort_by_cache_likelihood: Whether to prioritize likely cache hits

        Returns:
            List of ASIN lookup results in original book order
        """
        if parallel is None:
            parallel = self.max_parallel

        self.logger.info(
            f"Starting intelligent batch ASIN lookup for {len(books)} books (parallel={parallel})"
        )

        # Create book processing queue with intelligent ordering
        book_queue = self._create_intelligent_book_queue(
            books, sort_by_cache_likelihood
        )

        # Track results with original indices to maintain order
        results = [None] * len(books)
        completed_count = 0

        def lookup_single_book_with_index(
            book_item: Tuple[int, Book],
        ) -> Tuple[int, ASINLookupResult]:
            """Lookup ASIN for a single book and return with original index."""
            original_index, book = book_item

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

                return original_index, result

            except Exception as e:
                self.logger.error(f"Failed to lookup ASIN for book '{book.title}': {e}")
                return original_index, ASINLookupResult(
                    query_title=book.title,
                    query_author=book.author,
                    asin=None,
                    metadata=None,
                    source=None,
                    success=False,
                    error=str(e),
                )

        # Use ThreadPoolExecutor for intelligent parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            # Submit all jobs to executor
            futures = []
            for book_item in book_queue:
                future = executor.submit(lookup_single_book_with_index, book_item)
                futures.append(future)

            # Process results as they complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    original_index, result = future.result()
                    results[original_index] = result
                    completed_count += 1

                    if progress_callback:
                        progress_callback(
                            description=f"Completed lookup {completed_count}/{len(books)}: {result.query_title}"
                        )

                except Exception as e:
                    self.logger.error(f"Batch lookup future failed: {e}")
                    # We'll handle missing results after the loop
                    completed_count += 1

        # Handle any missing results (shouldn't happen but just in case)
        for i, result in enumerate(results):
            if result is None:
                book = books[i]
                results[i] = ASINLookupResult(
                    query_title=book.title,
                    query_author=book.author,
                    asin=None,
                    metadata=None,
                    source=None,
                    success=False,
                    error="Lookup failed to complete",
                )

        successful_lookups = sum(1 for r in results if r and r.success)
        cache_hits = sum(1 for r in results if r and r.from_cache)
        self.logger.info(
            f"Batch ASIN lookup completed: {successful_lookups}/{len(books)} successful ({cache_hits} from cache)"
        )

        return results

    def _create_intelligent_book_queue(
        self, books: List[Book], sort_by_cache_likelihood: bool
    ) -> List[Tuple[int, Book]]:
        """
        Create intelligently ordered book queue for batch processing.

        Prioritizes books likely to be in cache for faster processing.
        """
        book_items = [(i, book) for i, book in enumerate(books)]

        if not sort_by_cache_likelihood:
            return book_items

        def cache_likelihood_score(book_item: Tuple[int, Book]) -> float:
            """Calculate likelihood that this book will have a cache hit."""
            _, book = book_item
            score = 0.0

            # ISBN gives highest cache likelihood
            if book.isbn:
                cache_key = f"isbn_{book.isbn}".lower()
                if self.cache_manager.get_cached_asin(cache_key):
                    return 10.0  # Definite cache hit
                score += 3.0  # ISBN is more likely to be cached

            # Title/author combination
            if book.title and book.author:
                cache_key = f"{book.title}_{book.author}".lower().strip()
                if self.cache_manager.get_cached_asin(cache_key):
                    return 10.0  # Definite cache hit
                score += 2.0
            elif book.title:
                cache_key = f"{book.title}_".lower().strip()
                if self.cache_manager.get_cached_asin(cache_key):
                    return 10.0  # Definite cache hit
                score += 1.0

            # Popular authors/series more likely to be cached
            if book.author:
                author_lower = book.author.lower()
                popular_authors = [
                    "brandon sanderson",
                    "stephen king",
                    "j.k. rowling",
                    "george r.r. martin",
                ]
                if any(author in author_lower for author in popular_authors):
                    score += 1.0

            return score

        # Sort by cache likelihood (highest first) while preserving original indices
        try:
            sorted_items = sorted(book_items, key=cache_likelihood_score, reverse=True)
            self.logger.debug(
                f"Sorted {len(books)} books by cache likelihood for batch processing"
            )
            return sorted_items
        except Exception as e:
            self.logger.warning(
                f"Failed to sort books by cache likelihood: {e}, using original order"
            )
            return book_items

    def validate_asin(self, asin: str) -> bool:
        """Validate ASIN format - specifically for Amazon ASINs (not ISBNs)."""
        if not asin or not isinstance(asin, str):
            return False

        # Amazon ASINs for books start with 'B' and are exactly 10 characters
        # Pattern: B followed by 9 alphanumeric characters
        asin_pattern = re.compile(r"^B[A-Z0-9]{9}$")
        return bool(asin_pattern.match(asin.upper()))

    def calculate_result_confidence(
        self,
        asin: str,
        source: str,
        query_title: str,
        query_author: Optional[str] = None,
        query_isbn: Optional[str] = None,
    ) -> float:
        """
        Calculate confidence score for an ASIN lookup result.

        Args:
            asin: The ASIN found
            source: Source where ASIN was found
            query_title: Title that was searched
            query_author: Author that was searched (optional)
            query_isbn: ISBN that was searched (optional)

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.0

        # Base confidence by source reliability
        source_confidence = {
            "isbn-direct": 0.95,  # ISBN redirect very reliable
            "amazon-search": 0.75,  # Web scraping less reliable
            "google-books": 0.85,  # API more reliable than scraping
            "openlibrary": 0.70,  # Lower reliability
            "cache": 1.0,  # Cache is perfect if valid
        }
        confidence = source_confidence.get(source, 0.5)

        # ASIN format validation
        if not self.validate_asin(asin):
            confidence *= 0.1  # Very low confidence for invalid format
            return max(0.0, min(1.0, confidence))

        # Query type confidence adjustments
        if query_isbn:
            # ISBN queries are most reliable
            confidence += 0.1
        elif query_title and query_author:
            # Title + author is good
            confidence += 0.05
        elif query_title:
            # Title only is less reliable
            confidence -= 0.05

        # Title/author matching quality (if we had metadata to compare)
        # This would be enhanced with actual result metadata comparison
        # For now, we use basic heuristics

        # Historical source success rate adjustment
        rate_stats = self.rate_limiter.get_domain_stats(
            "amazon.com" if "amazon" in source else "googleapis.com"
        )
        if rate_stats.get("requests_made", 0) > 0:
            success_rate = 1.0 - (
                rate_stats.get("backoffs_triggered", 0)
                / max(1, rate_stats.get("requests_made", 1))
            )
            confidence *= 0.8 + 0.2 * success_rate  # Factor in recent success rate

        # Ensure confidence is within bounds
        return max(0.0, min(1.0, confidence))

    def should_try_more_sources(
        self,
        current_result: Optional[ASINLookupResult],
        confidence_threshold: float = 0.85,
    ) -> bool:
        """
        Determine if we should try more sources based on current result confidence.

        Args:
            current_result: Current best result
            confidence_threshold: Minimum confidence to stop searching

        Returns:
            True if we should try more sources, False to stop early
        """
        if not current_result or not current_result.success:
            return True  # No result yet, keep trying

        # Calculate confidence for current result
        confidence = self.calculate_result_confidence(
            current_result.asin,
            current_result.source,
            current_result.query_title,
            current_result.query_author,
        )

        # Stop if confidence is high enough
        return confidence < confidence_threshold

    def check_availability(self, asin: str, progress_callback=None):
        """Check if ASIN is available on Amazon."""
        self.logger.info(f"Checking availability for ASIN: {asin}")

        if progress_callback:
            progress_callback(description=f"Checking availability for {asin}...")

        try:
            # Simple availability check by accessing Amazon product page
            url = f"https://www.amazon.com/dp/{asin}"
            headers = {"User-Agent": self.user_agents[0]}

            response = self.http_session.get(
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
        """Direct ISBN to ASIN lookup via Amazon redirect."""
        if not isbn:
            return None

        # Clean ISBN
        clean_isbn = re.sub(r"[^0-9X]", "", isbn.upper())

        try:
            # Try Amazon ISBN redirect
            url = f"https://www.amazon.com/dp/{clean_isbn}"
            headers = {"User-Agent": self.user_agents[0]}

            response = self.http_session.get(
                url, headers=headers, allow_redirects=True, timeout=10
            )

            if response.status_code == 200:
                # Look for ASIN in the final URL
                final_url = response.url
                asin_match = re.search(r"/dp/([B][A-Z0-9]{9})", final_url)

                if asin_match:
                    return asin_match.group(1)

        except Exception as e:
            self.logger.debug(f"ISBN direct lookup failed: {e}")

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

                        response = self.http_session.get(
                            url, headers=headers, timeout=15
                        )

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
                                f"Amazon search: Service unavailable (503), retrying with different user agent"
                            )
                            time.sleep(2**attempt)  # Exponential backoff
                            continue
                        elif response.status_code == 429:
                            self.logger.debug(
                                f"Amazon search: Rate limited (429), backing off"
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
    ) -> Optional[str]:
        """Google Books API lookup with improved query formatting and multiple strategies."""

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
            return None

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

                        response = self.http_session.get(
                            url, headers=headers, timeout=15
                        )

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
                                        f"Google Books ({strategy_name}): Result {i+1}: '{title_found}' by {authors_found} ({published_date})"
                                    )

                            # Try different ASIN extraction methods
                            asin_found = self._extract_asin_from_google_books_result(
                                data, verbose, strategy_name
                            )
                            if asin_found:
                                return asin_found

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
        return None

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

                response = self.http_session.get(url, timeout=10)

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

                search_response = self.http_session.get(search_url, timeout=10)

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
                                f"OpenLibrary: Search result {i+1}: '{doc_title}' by {doc_author}"
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

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        # Get cache stats
        cache_stats = self.cache_manager.get_stats()

        # Get rate limiter stats
        rate_limit_stats = self.rate_limiter.get_all_stats()

        return {
            "cache": cache_stats,
            "rate_limiting": rate_limit_stats,
            "configuration": {
                "sources": self.sources,
                "max_parallel": self.max_parallel,
                "connection_pool_size": self.connection_pool_size,
                "cache_backend": self.cache_backend,
                "cache_ttl_days": self.cache_ttl_days,
            },
        }

    def close(self):
        """Clean up resources."""
        if hasattr(self, "http_session"):
            self.http_session.close()
        if hasattr(self, "cache_manager"):
            self.cache_manager.close()

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.close()


# Backward compatibility alias for tests
# Import cache managers for test compatibility
from .cache import SQLiteCacheManager, JSONCacheManager

# Default to JSONCacheManager for backward compatibility with tests
# Tests expect JSON-based API with cache_data attribute
CacheManager = JSONCacheManager
