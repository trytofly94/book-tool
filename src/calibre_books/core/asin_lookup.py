"""
ASIN lookup service for Calibre Books CLI.

This module provides functionality for looking up Amazon ASINs
from various sources including Amazon, Goodreads, and OpenLibrary.

Integrates the enhanced_asin_lookup.py functionality into the new CLI architecture.
"""

import logging
import requests
import time
import re
import json
import os
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
import concurrent.futures
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from ..utils.logging import LoggerMixin
from .book import Book, ASINLookupResult


class ASINLookupService(LoggerMixin):
    """
    ASIN lookup service.
    
    Provides methods for looking up ASINs from multiple sources
    with caching and rate limiting.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ASIN lookup service.
        
        Args:
            config: ASIN lookup configuration dictionary
        """
        super().__init__()
        self.config = config
        self.cache_path = Path(config.get('cache_path', '~/.book-tool/asin_cache.json')).expanduser()
        self.sources = config.get('sources', ['amazon', 'goodreads', 'openlibrary'])
        self.rate_limit = config.get('rate_limit', 2.0)
        
        self.logger.info(f"Initialized ASIN lookup service with sources: {self.sources}")
        
        # Initialize cache manager
        self.cache_manager = CacheManager(self.cache_path)
        
        # User agents for web scraping
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        # Thread lock for cache operations
        self._cache_lock = threading.Lock()
    
    def lookup_by_title(
        self,
        title: str,
        author: Optional[str] = None,
        sources: Optional[List[str]] = None,
        use_cache: bool = True,
        progress_callback=None,
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
        self.logger.info(f"Looking up ASIN for '{title}' by {author or 'unknown author'}")
        
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
                    from_cache=True
                )
        
        # Use provided sources or default configuration sources
        search_sources = sources or self.sources
        
        # Try different lookup methods in priority order
        lookup_methods = [
            ('amazon-search', lambda: self._lookup_via_amazon_search(title, author)),
            ('google-books', lambda: self._lookup_via_google_books(None, title, author)),
            ('openlibrary', lambda: self._lookup_via_openlibrary(None) if author else None),
        ]
        
        for method_name, method in lookup_methods:
            # Skip if source not in requested sources
            if not any(source in method_name for source in search_sources):
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
                        query_title=title,
                        query_author=author,
                        asin=asin,
                        metadata=None,
                        source=method_name,
                        success=True,
                        lookup_time=time.time() - start_time,
                        from_cache=False
                    )
                
                # Rate limiting between attempts
                time.sleep(self.rate_limit)
                
            except Exception as e:
                self.logger.warning(f"Lookup method {method_name} failed: {e}")
                continue
        
        # No ASIN found
        self.logger.info(f"No ASIN found for '{title}' by {author or 'unknown author'}")
        return ASINLookupResult(
            query_title=title,
            query_author=author,
            asin=None,
            metadata=None,
            source=None,
            success=False,
            error="No ASIN found from any source",
            lookup_time=time.time() - start_time,
            from_cache=False
        )
    
    def lookup_by_isbn(
        self,
        isbn: str,
        sources: Optional[List[str]] = None,
        use_cache: bool = True,
        progress_callback=None,
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
                    from_cache=True
                )
        
        # Use provided sources or default configuration sources
        search_sources = sources or self.sources
        
        # Try different lookup methods in priority order for ISBN
        lookup_methods = [
            ('isbn-direct', lambda: self._lookup_by_isbn_direct(isbn)),
            ('google-books', lambda: self._lookup_via_google_books(isbn, None, None)),
            ('openlibrary', lambda: self._lookup_via_openlibrary(isbn)),
        ]
        
        for method_name, method in lookup_methods:
            # Skip if source not in requested sources
            if not any(source in method_name for source in search_sources):
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
                        from_cache=False
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
            from_cache=False
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
                        progress_callback=None  # No individual progress for batch
                    )
                else:
                    result = self.lookup_by_title(
                        book.title,
                        author=book.author,
                        sources=sources,
                        use_cache=True,
                        progress_callback=None  # No individual progress for batch
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
                    error=str(e)
                )
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = []
            
            for i, book in enumerate(books):
                future = executor.submit(lookup_single_book, book)
                futures.append(future)
                
                # Update progress if callback provided
                if progress_callback:
                    progress_callback(description=f"Submitted lookup {i+1}/{len(books)}: {book.title}")
                
                # Stagger requests to respect rate limits
                time.sleep(self.rate_limit / parallel)
            
            # Collect results as they complete
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    result = future.result()
                    results.append(result)
                    
                    if progress_callback:
                        progress_callback(description=f"Completed lookup {len(results)}/{len(books)}")
                        
                except Exception as e:
                    self.logger.error(f"Batch lookup failed for future {i}: {e}")
                    # Create a failed result
                    results.append(ASINLookupResult(
                        query_title="Unknown",
                        query_author=None,
                        asin=None,
                        metadata=None,
                        source=None,
                        success=False,
                        error=str(e)
                    ))
        
        successful_lookups = sum(1 for r in results if r.success)
        self.logger.info(f"Batch ASIN lookup completed: {successful_lookups}/{len(books)} successful")
        
        return results
    
    def validate_asin(self, asin: str) -> bool:
        """Validate ASIN format."""
        from ..utils.validation import validate_asin
        return validate_asin(asin)
    
    def check_availability(self, asin: str, progress_callback=None):
        """Check if ASIN is available on Amazon."""
        self.logger.info(f"Checking availability for ASIN: {asin}")
        
        if progress_callback:
            progress_callback(description=f"Checking availability for {asin}...")
        
        try:
            # Simple availability check by accessing Amazon product page
            url = f"https://www.amazon.com/dp/{asin}"
            headers = {'User-Agent': self.user_agents[0]}
            
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            
            # Check if we got a valid product page
            if response.status_code == 200:
                # Look for signs that the product exists and is available
                content = response.text.lower()
                
                # Basic availability indicators
                if 'currently unavailable' in content or 'page not found' in content:
                    available = False
                    metadata = {'status': 'unavailable'}
                else:
                    available = True
                    metadata = {'status': 'available', 'url': response.url}
            else:
                available = False
                metadata = {'status': 'not_found', 'status_code': response.status_code}
                
        except Exception as e:
            self.logger.error(f"Availability check failed for {asin}: {e}")
            available = False
            metadata = {'status': 'error', 'error': str(e)}
        
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
        clean_isbn = re.sub(r'[^0-9X]', '', isbn.upper())
        
        try:
            # Try Amazon ISBN redirect
            url = f"https://www.amazon.com/dp/{clean_isbn}"
            headers = {'User-Agent': self.user_agents[0]}
            
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
            
            if response.status_code == 200:
                # Look for ASIN in the final URL
                final_url = response.url
                asin_match = re.search(r'/dp/([B][A-Z0-9]{9})', final_url)
                
                if asin_match:
                    return asin_match.group(1)
                
        except Exception as e:
            self.logger.debug(f"ISBN direct lookup failed: {e}")
        
        return None
    
    def _lookup_via_amazon_search(self, title: str, author: Optional[str]) -> Optional[str]:
        """Web scraping of Amazon search results."""
        if not title:
            return None
        
        try:
            # Create search query
            query = title
            if author:
                query = f"{title} {author}"
            
            query = query.replace(' ', '+')
            url = f"https://www.amazon.com/s?k={query}&i=digital-text"
            
            headers = {'User-Agent': self.user_agents[0]}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for products with data-asin attribute
                products = soup.find_all(attrs={'data-asin': True})
                
                for product in products:
                    asin = product.get('data-asin')
                    if asin and asin.startswith('B') and len(asin) == 10:
                        return asin
                        
        except Exception as e:
            self.logger.debug(f"Amazon search lookup failed: {e}")
        
        return None
    
    def _lookup_via_google_books(self, isbn: Optional[str], title: Optional[str], author: Optional[str]) -> Optional[str]:
        """Google Books API lookup."""
        try:
            # Build search query
            query_parts = []
            if isbn:
                query_parts.append(f"isbn:{isbn}")
            if title:
                query_parts.append(f'intitle:"{title}"')
            if author:
                query_parts.append(f'inauthor:"{author}"')
            
            if not query_parts:
                return None
            
            query = '+'.join(query_parts)
            url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=5"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get('items', []):
                    volume_info = item.get('volumeInfo', {})
                    industry_identifiers = volume_info.get('industryIdentifiers', [])
                    
                    # Look for ASIN in identifiers
                    for identifier in industry_identifiers:
                        if identifier.get('type') == 'OTHER':
                            asin_candidate = identifier.get('identifier', '')
                            if self.validate_asin(asin_candidate):
                                return asin_candidate
                                
        except Exception as e:
            self.logger.debug(f"Google Books lookup failed: {e}")
        
        return None
    
    def _lookup_via_openlibrary(self, isbn: Optional[str]) -> Optional[str]:
        """OpenLibrary API lookup."""
        if not isbn:
            return None
        
        try:
            clean_isbn = re.sub(r'[^0-9X]', '', isbn.upper())
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # OpenLibrary rarely has ASINs, but check identifiers
                for book_data in data.values():
                    identifiers = book_data.get('identifiers', {})
                    
                    # Look for Amazon identifiers
                    amazon_ids = identifiers.get('amazon', [])
                    for amazon_id in amazon_ids:
                        if self.validate_asin(amazon_id):
                            return amazon_id
                            
        except Exception as e:
            self.logger.debug(f"OpenLibrary lookup failed: {e}")
        
        return None


class CacheManager:
    """Manages ASIN lookup cache."""
    
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.cache_data = {}
        self._cache_lock = threading.Lock()
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from file."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f:
                    self.cache_data = json.load(f)
            except Exception:
                self.cache_data = {}
        else:
            self.cache_data = {}
            # Ensure cache directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _save_cache(self):
        """Save cache to file."""
        try:
            with open(self.cache_path, 'w') as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception:
            pass  # Ignore cache save errors
    
    def get_cached_asin(self, cache_key: str) -> Optional[str]:
        """Get cached ASIN for key."""
        with self._cache_lock:
            return self.cache_data.get(cache_key)
    
    def cache_asin(self, cache_key: str, asin: str):
        """Cache an ASIN."""
        with self._cache_lock:
            self.cache_data[cache_key] = asin
            self._save_cache()
    
    def get_stats(self):
        """Get cache statistics."""
        from dataclasses import dataclass
        from datetime import datetime
        
        @dataclass
        class Stats:
            total_entries: int = 0
            hit_rate: float = 0.0
            size_human: str = "0 B"
            last_updated: datetime = datetime.now()
        
        with self._cache_lock:
            total_entries = len(self.cache_data)
            
            # Calculate cache file size
            if self.cache_path.exists():
                size_bytes = self.cache_path.stat().st_size
                last_updated = datetime.fromtimestamp(self.cache_path.stat().st_mtime)
            else:
                size_bytes = 0
                last_updated = datetime.now()
            
            # Human readable size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    size_human = f"{size_bytes:.1f} {unit}"
                    break
                size_bytes /= 1024.0
            else:
                size_human = f"{size_bytes:.1f} TB"
        
        return Stats(
            total_entries=total_entries,
            hit_rate=0.0,  # Would need to track hits/misses for real calculation
            size_human=size_human,
            last_updated=last_updated
        )
    
    def clear(self):
        """Clear all cached entries."""
        with self._cache_lock:
            self.cache_data = {}
            self._save_cache()
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries."""
        # For now, we don't implement expiration
        # Could be added later with timestamp tracking
        return 0