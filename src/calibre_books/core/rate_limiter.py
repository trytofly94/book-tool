"""
Rate limiting for ASIN lookup APIs with per-domain token bucket algorithm.

This module provides intelligent rate limiting that respects different API limits
for various sources while implementing exponential backoff and error recovery.
"""

import time
import threading
import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import requests


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a specific domain/API."""
    requests_per_second: float = 1.0
    max_tokens: int = 10
    backoff_factor: float = 2.0
    max_backoff_delay: float = 300.0  # 5 minutes max
    burst_allowance: int = 5  # Allow bursts of N requests
    cooldown_period: float = 60.0  # Seconds to cool down after rate limit hit


@dataclass  
class TokenBucket:
    """Token bucket for rate limiting with thread-safe operations."""
    capacity: int
    tokens: float
    fill_rate: float  # tokens per second
    last_update: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)
    
    def __post_init__(self):
        """Initialize tokens to full capacity."""
        if self.tokens == 0:
            self.tokens = self.capacity
    
    def consume(self, tokens_needed: int = 1) -> bool:
        """
        Try to consume tokens from bucket.
        
        Args:
            tokens_needed: Number of tokens to consume
            
        Returns:
            True if tokens were available and consumed, False otherwise
        """
        with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            
            # Add tokens based on time passed
            self.tokens = min(self.capacity, self.tokens + time_passed * self.fill_rate)
            self.last_update = now
            
            # Try to consume tokens
            if self.tokens >= tokens_needed:
                self.tokens -= tokens_needed
                return True
            else:
                return False
    
    def time_until_available(self, tokens_needed: int = 1) -> float:
        """
        Calculate time until requested tokens will be available.
        
        Args:
            tokens_needed: Number of tokens needed
            
        Returns:
            Seconds until tokens will be available
        """
        with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            
            # Calculate current token count
            current_tokens = min(self.capacity, self.tokens + time_passed * self.fill_rate)
            
            if current_tokens >= tokens_needed:
                return 0.0
            
            # Calculate time needed to generate missing tokens
            tokens_missing = tokens_needed - current_tokens
            return tokens_missing / self.fill_rate
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bucket status."""
        with self.lock:
            now = time.time()
            time_passed = now - self.last_update
            current_tokens = min(self.capacity, self.tokens + time_passed * self.fill_rate)
            
            return {
                'current_tokens': round(current_tokens, 2),
                'capacity': self.capacity,
                'fill_rate': self.fill_rate,
                'utilization': round((self.capacity - current_tokens) / self.capacity * 100, 1)
            }


class DomainRateLimiter:
    """
    Per-domain rate limiter with token bucket algorithm and adaptive backoff.
    
    Handles rate limiting for different API endpoints with domain-specific
    limits and intelligent error recovery.
    """
    
    # Default configurations for known APIs
    DEFAULT_CONFIGS = {
        'amazon.com': RateLimitConfig(
            requests_per_second=1.0,  # Conservative for scraping
            max_tokens=5,
            backoff_factor=2.0,
            max_backoff_delay=600.0  # 10 minutes for Amazon
        ),
        'googleapis.com': RateLimitConfig(
            requests_per_second=10.0,  # Google Books API allows more
            max_tokens=100,
            backoff_factor=1.5,
            burst_allowance=20
        ),
        'openlibrary.org': RateLimitConfig(
            requests_per_second=5.0,  # OpenLibrary is more permissive
            max_tokens=25,
            backoff_factor=1.5,
            burst_allowance=10
        ),
        'default': RateLimitConfig(
            requests_per_second=2.0,
            max_tokens=10,
            backoff_factor=2.0
        )
    }
    
    def __init__(self, custom_configs: Optional[Dict[str, RateLimitConfig]] = None):
        """
        Initialize rate limiter with optional custom configurations.
        
        Args:
            custom_configs: Custom rate limit configurations by domain
        """
        self.logger = logging.getLogger(__name__)
        
        # Merge default and custom configurations
        self.configs = self.DEFAULT_CONFIGS.copy()
        if custom_configs:
            self.configs.update(custom_configs)
        
        # Token buckets per domain
        self.buckets: Dict[str, TokenBucket] = {}
        self.bucket_lock = threading.Lock()
        
        # Backoff tracking per domain
        self.backoff_state: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'current_delay': 0.0,
            'consecutive_failures': 0,
            'last_failure_time': 0.0,
            'in_cooldown': False
        })
        
        # Statistics tracking
        self.stats = defaultdict(lambda: {
            'requests_made': 0,
            'requests_limited': 0,
            'backoffs_triggered': 0,
            'total_delay_time': 0.0,
            'last_request_time': 0.0
        })
    
    def _get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL for rate limiting."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Map common domains to their rate limit keys
            if 'amazon' in domain:
                return 'amazon.com'
            elif 'googleapis.com' in domain or 'google' in domain:
                return 'googleapis.com'
            elif 'openlibrary.org' in domain:
                return 'openlibrary.org'
            else:
                return domain if domain else 'default'
                
        except Exception:
            return 'default'
    
    def _get_bucket(self, domain: str) -> TokenBucket:
        """Get or create token bucket for domain."""
        with self.bucket_lock:
            if domain not in self.buckets:
                config = self.configs.get(domain, self.configs['default'])
                self.buckets[domain] = TokenBucket(
                    capacity=config.max_tokens,
                    tokens=config.max_tokens,
                    fill_rate=config.requests_per_second
                )
                self.logger.debug(f"Created token bucket for {domain}: {config.requests_per_second} req/s")
            
            return self.buckets[domain]
    
    def wait_for_request(self, url: str) -> float:
        """
        Wait for rate limit before making request.
        
        Args:
            url: URL to be requested
            
        Returns:
            Time waited in seconds
        """
        domain = self._get_domain_from_url(url)
        config = self.configs.get(domain, self.configs['default'])
        bucket = self._get_bucket(domain)
        
        start_time = time.time()
        
        # Check if we're in cooldown period
        backoff_info = self.backoff_state[domain]
        if backoff_info['in_cooldown']:
            cooldown_remaining = (backoff_info['last_failure_time'] + config.cooldown_period) - time.time()
            if cooldown_remaining > 0:
                self.logger.debug(f"Domain {domain} in cooldown, waiting {cooldown_remaining:.1f}s")
                time.sleep(cooldown_remaining)
            else:
                backoff_info['in_cooldown'] = False
                backoff_info['consecutive_failures'] = 0
                backoff_info['current_delay'] = 0.0
        
        # Try to consume token from bucket
        if not bucket.consume(1):
            # Need to wait for tokens
            wait_time = bucket.time_until_available(1)
            self.logger.debug(f"Rate limited for {domain}, waiting {wait_time:.2f}s")
            
            time.sleep(wait_time)
            
            # Try again after waiting
            if not bucket.consume(1):
                # Still no tokens, add small additional delay
                additional_wait = 1.0 / config.requests_per_second
                time.sleep(additional_wait)
                wait_time += additional_wait
            
            self.stats[domain]['requests_limited'] += 1
        
        total_wait = time.time() - start_time
        self.stats[domain]['total_delay_time'] += total_wait
        self.stats[domain]['last_request_time'] = time.time()
        
        return total_wait
    
    def handle_response(self, url: str, response: requests.Response) -> Optional[float]:
        """
        Handle API response and adjust rate limiting if needed.
        
        Args:
            url: URL that was requested
            response: HTTP response received
            
        Returns:
            Additional delay time if backoff is needed, None otherwise
        """
        domain = self._get_domain_from_url(url)
        config = self.configs.get(domain, self.configs['default'])
        backoff_info = self.backoff_state[domain]
        
        self.stats[domain]['requests_made'] += 1
        
        # Handle rate limit responses
        if response.status_code == 429:  # Too Many Requests
            self.logger.warning(f"Rate limit hit for {domain}")
            return self._trigger_backoff(domain, config, 'rate_limit')
        
        elif response.status_code == 503:  # Service Unavailable
            self.logger.warning(f"Service unavailable for {domain}")
            return self._trigger_backoff(domain, config, 'service_unavailable')
        
        elif response.status_code >= 500:  # Server errors
            self.logger.warning(f"Server error {response.status_code} for {domain}")
            return self._trigger_backoff(domain, config, 'server_error')
        
        else:
            # Success - reset backoff state
            if backoff_info['consecutive_failures'] > 0:
                self.logger.info(f"Recovered from failures for {domain}")
                backoff_info['consecutive_failures'] = 0
                backoff_info['current_delay'] = 0.0
                backoff_info['in_cooldown'] = False
            
            return None
    
    def _trigger_backoff(self, domain: str, config: RateLimitConfig, reason: str) -> float:
        """
        Trigger exponential backoff for domain.
        
        Args:
            domain: Domain to apply backoff to
            config: Rate limit configuration
            reason: Reason for backoff
            
        Returns:
            Delay time in seconds
        """
        backoff_info = self.backoff_state[domain]
        backoff_info['consecutive_failures'] += 1
        backoff_info['last_failure_time'] = time.time()
        
        # Calculate exponential backoff delay
        base_delay = 1.0 / config.requests_per_second
        exponential_delay = base_delay * (config.backoff_factor ** backoff_info['consecutive_failures'])
        delay = min(exponential_delay, config.max_backoff_delay)
        
        backoff_info['current_delay'] = delay
        self.stats[domain]['backoffs_triggered'] += 1
        
        # Enter cooldown if too many consecutive failures
        if backoff_info['consecutive_failures'] >= 3:
            backoff_info['in_cooldown'] = True
            self.logger.warning(f"Entering cooldown for {domain} after {backoff_info['consecutive_failures']} failures")
        
        self.logger.info(f"Backing off {delay:.1f}s for {domain} (reason: {reason})")
        time.sleep(delay)
        
        return delay
    
    def get_domain_stats(self, domain: str) -> Dict[str, Any]:
        """Get statistics for specific domain."""
        bucket = self.buckets.get(domain)
        bucket_status = bucket.get_status() if bucket else {}
        
        stats = self.stats[domain].copy()
        backoff_info = self.backoff_state[domain]
        
        return {
            'domain': domain,
            'requests_made': stats['requests_made'],
            'requests_limited': stats['requests_limited'],
            'backoffs_triggered': stats['backoffs_triggered'],
            'total_delay_time': round(stats['total_delay_time'], 2),
            'average_delay': round(stats['total_delay_time'] / max(1, stats['requests_made']), 3),
            'last_request_time': stats['last_request_time'],
            'consecutive_failures': backoff_info['consecutive_failures'],
            'current_delay': backoff_info['current_delay'],
            'in_cooldown': backoff_info['in_cooldown'],
            'bucket_status': bucket_status
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all domains."""
        return {domain: self.get_domain_stats(domain) for domain in self.stats.keys()}
    
    def reset_domain(self, domain: str):
        """Reset rate limiting state for domain."""
        with self.bucket_lock:
            if domain in self.buckets:
                config = self.configs.get(domain, self.configs['default'])
                self.buckets[domain] = TokenBucket(
                    capacity=config.max_tokens,
                    tokens=config.max_tokens,
                    fill_rate=config.requests_per_second
                )
        
        # Reset backoff state
        self.backoff_state[domain] = {
            'current_delay': 0.0,
            'consecutive_failures': 0,
            'last_failure_time': 0.0,
            'in_cooldown': False
        }
        
        # Reset stats
        self.stats[domain] = {
            'requests_made': 0,
            'requests_limited': 0,
            'backoffs_triggered': 0,
            'total_delay_time': 0.0,
            'last_request_time': 0.0
        }
        
        self.logger.info(f"Reset rate limiting state for {domain}")


class RateLimitedSession:
    """
    HTTP session wrapper with automatic rate limiting and connection pooling.
    
    Combines rate limiting with connection reuse for optimal performance.
    """
    
    def __init__(self, rate_limiter: DomainRateLimiter, pool_connections: int = 10, pool_maxsize: int = 20):
        """
        Initialize rate limited session.
        
        Args:
            rate_limiter: Rate limiter instance
            pool_connections: Number of connection pools to cache
            pool_maxsize: Maximum connections per pool
        """
        self.rate_limiter = rate_limiter
        self.logger = logging.getLogger(__name__)
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Set default timeouts and headers
        self.session.timeout = 30
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """Rate-limited GET request with automatic retry."""
        return self._request('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """Rate-limited POST request with automatic retry."""
        return self._request('POST', url, **kwargs)
    
    def _request(self, method: str, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
        """
        Make rate-limited HTTP request with automatic retry.
        
        Args:
            method: HTTP method
            url: URL to request
            max_retries: Maximum number of retries
            **kwargs: Additional arguments for requests
            
        Returns:
            HTTP response
            
        Raises:
            requests.RequestException: If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Wait for rate limiter
                wait_time = self.rate_limiter.wait_for_request(url)
                if wait_time > 0:
                    self.logger.debug(f"Waited {wait_time:.2f}s for rate limit")
                
                # Make request
                response = self.session.request(method, url, **kwargs)
                
                # Handle response with rate limiter
                additional_delay = self.rate_limiter.handle_response(url, response)
                if additional_delay:
                    self.logger.debug(f"Additional backoff delay: {additional_delay:.2f}s")
                
                # Return response even if it's an error (let caller handle)
                return response
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                
                if attempt < max_retries:
                    delay = 2 ** attempt  # Exponential backoff
                    self.logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}, retrying in {delay}s")
                    time.sleep(delay)
                else:
                    self.logger.error(f"Request failed after {max_retries + 1} attempts: {e}")
        
        # All retries exhausted
        raise last_exception
    
    def close(self):
        """Close the session."""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()