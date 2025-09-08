"""
Cache management for ASIN lookups with SQLite backend and performance optimizations.

This module provides high-performance caching with TTL support, concurrent access,
and migration from JSON-based caches for backward compatibility.
"""

import sqlite3
import json
import threading
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from contextlib import contextmanager


class SQLiteCacheManager:
    """
    High-performance SQLite-based cache manager for ASIN lookups.

    Features:
    - O(1) cache lookups with proper indexing
    - TTL-based expiration policies
    - Concurrent access with WAL mode
    - Automatic migration from JSON caches
    - Cache statistics and monitoring
    - Connection pooling for better performance
    """

    def __init__(self, cache_path: Path, ttl_days: int = 30, auto_cleanup: bool = True):
        """
        Initialize SQLite cache manager.

        Args:
            cache_path: Path to SQLite cache database
            ttl_days: Time-to-live for cache entries in days
            auto_cleanup: Whether to automatically cleanup expired entries
        """
        self.cache_path = cache_path
        self.ttl_days = ttl_days
        self.auto_cleanup = auto_cleanup
        self.logger = logging.getLogger(__name__)

        # Thread-safe connection handling
        self._local = threading.local()
        self._cache_lock = threading.Lock()

        # Statistics tracking
        self._stats = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "cleanup_runs": 0,
            "migrated_entries": 0,
        }

        # Initialize database
        self._init_database()

        # Check for JSON cache migration
        self._migrate_from_json_cache()

        # Auto cleanup if enabled
        if self.auto_cleanup:
            self.cleanup_expired()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection with proper configuration."""
        if not hasattr(self._local, "connection"):
            # Ensure cache directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Create connection with performance optimizations
            conn = sqlite3.connect(
                str(self.cache_path),
                timeout=30.0,  # 30-second timeout for locked database
                isolation_level=None,  # Autocommit mode
                check_same_thread=False,
            )

            # Performance optimizations
            conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
            conn.execute(
                "PRAGMA synchronous=NORMAL"
            )  # Balance between safety and speed
            conn.execute("PRAGMA cache_size=10000")  # 10MB cache
            conn.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp tables
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory mapping

            self._local.connection = conn

        return self._local.connection

    @contextmanager
    def _get_cursor(self):
        """Context manager for database operations."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def _init_database(self):
        """Initialize database schema with proper indexing."""
        try:
            with self._get_cursor() as cursor:
                # Create main cache table with optimized schema
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS asin_cache (
                        cache_key TEXT PRIMARY KEY,
                        asin TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        source TEXT,
                        confidence_score REAL DEFAULT 1.0,
                        access_count INTEGER DEFAULT 1,
                        last_accessed REAL NOT NULL
                    )
                """
                )

                # Create indexes for performance
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_expires_at ON asin_cache(expires_at)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_source ON asin_cache(source)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_confidence ON asin_cache(confidence_score)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_last_accessed ON asin_cache(last_accessed)"
                )

                # Create statistics table for tracking cache performance
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache_stats (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """
                )

                self.logger.debug(
                    f"Initialized SQLite cache database: {self.cache_path}"
                )

        except sqlite3.Error as e:
            self.logger.error(f"Failed to initialize cache database: {e}")
            raise

    def _migrate_from_json_cache(self):
        """Migrate existing JSON cache to SQLite with validation."""
        # Look for JSON cache in various possible locations
        possible_json_paths = [
            self.cache_path.parent / "asin_cache.json",
            Path("~/.book-tool/asin_cache.json").expanduser(),
            Path.cwd() / "asin_cache.json",
            # Legacy paths
            Path("/tmp/asin_cache.json"),
        ]

        migrated_count = 0

        for json_path in possible_json_paths:
            if json_path.exists():
                try:
                    self.logger.info(f"Found JSON cache at {json_path}, migrating...")

                    with open(json_path, "r") as f:
                        json_data = json.load(f)

                    if not isinstance(json_data, dict):
                        self.logger.warning(
                            f"Invalid JSON cache format in {json_path}, skipping"
                        )
                        continue

                    # Batch insert for better performance
                    current_time = time.time()
                    expires_at = current_time + (self.ttl_days * 24 * 3600)

                    entries_to_migrate = []
                    for cache_key, asin in json_data.items():
                        if isinstance(asin, str) and asin.strip():
                            entries_to_migrate.append(
                                (
                                    cache_key,
                                    asin,
                                    current_time,
                                    expires_at,
                                    "migrated_json",
                                    1.0,  # confidence_score
                                    1,  # access_count
                                    current_time,  # last_accessed
                                )
                            )

                    if entries_to_migrate:
                        with self._get_cursor() as cursor:
                            cursor.executemany(
                                """
                                INSERT OR REPLACE INTO asin_cache 
                                (cache_key, asin, created_at, expires_at, source, confidence_score, access_count, last_accessed)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                entries_to_migrate,
                            )

                        migrated_count += len(entries_to_migrate)
                        self.logger.info(
                            f"Migrated {len(entries_to_migrate)} entries from {json_path}"
                        )

                    # Backup original JSON file before removal
                    backup_path = json_path.with_suffix(".json.backup")
                    json_path.rename(backup_path)
                    self.logger.info(f"Backed up original JSON cache to {backup_path}")

                except (json.JSONDecodeError, IOError, sqlite3.Error) as e:
                    self.logger.warning(
                        f"Failed to migrate JSON cache from {json_path}: {e}"
                    )
                    continue

        if migrated_count > 0:
            self._stats["migrated_entries"] = migrated_count
            self.logger.info(
                f"Successfully migrated {migrated_count} total cache entries from JSON to SQLite"
            )

    def get_cached_asin(self, cache_key: str) -> Optional[str]:
        """
        Get cached ASIN for key with automatic expiration checking.

        Args:
            cache_key: Cache key to lookup

        Returns:
            ASIN if found and not expired, None otherwise
        """
        try:
            current_time = time.time()

            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT asin, expires_at, access_count 
                    FROM asin_cache 
                    WHERE cache_key = ? AND expires_at > ?
                """,
                    (cache_key, current_time),
                )

                result = cursor.fetchone()

                if result:
                    asin, expires_at, access_count = result

                    # Update access statistics
                    cursor.execute(
                        """
                        UPDATE asin_cache 
                        SET access_count = access_count + 1, last_accessed = ?
                        WHERE cache_key = ?
                    """,
                        (current_time, cache_key),
                    )

                    self._stats["hits"] += 1
                    self.logger.debug(f"Cache hit for key: {cache_key}")
                    return asin
                else:
                    self._stats["misses"] += 1
                    self.logger.debug(f"Cache miss for key: {cache_key}")
                    return None

        except sqlite3.Error as e:
            self.logger.error(f"Cache lookup failed for key {cache_key}: {e}")
            self._stats["misses"] += 1
            return None

    def cache_asin(
        self,
        cache_key: str,
        asin: str,
        source: str = "unknown",
        confidence_score: float = 1.0,
    ):
        """
        Cache an ASIN with metadata and TTL.

        Args:
            cache_key: Cache key
            asin: ASIN to cache
            source: Source where ASIN was found
            confidence_score: Confidence score (0.0-1.0)
        """
        try:
            current_time = time.time()
            expires_at = current_time + (self.ttl_days * 24 * 3600)

            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO asin_cache 
                    (cache_key, asin, created_at, expires_at, source, confidence_score, access_count, last_accessed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cache_key,
                        asin,
                        current_time,
                        expires_at,
                        source,
                        confidence_score,
                        1,
                        current_time,
                    ),
                )

            self._stats["writes"] += 1
            self.logger.debug(
                f"Cached ASIN {asin} for key {cache_key} (source: {source}, confidence: {confidence_score})"
            )

        except sqlite3.Error as e:
            self.logger.error(f"Failed to cache ASIN for key {cache_key}: {e}")

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        try:
            current_time = time.time()

            with self._get_cursor() as cursor:
                # Count expired entries first
                cursor.execute(
                    "SELECT COUNT(*) FROM asin_cache WHERE expires_at <= ?",
                    (current_time,),
                )
                expired_count = cursor.fetchone()[0]

                if expired_count > 0:
                    # Delete expired entries
                    cursor.execute(
                        "DELETE FROM asin_cache WHERE expires_at <= ?", (current_time,)
                    )

                    # Vacuum database to reclaim space if significant cleanup
                    if expired_count > 100:
                        cursor.execute("VACUUM")

                    self._stats["cleanup_runs"] += 1
                    self.logger.info(
                        f"Cleaned up {expired_count} expired cache entries"
                    )

                return expired_count

        except sqlite3.Error as e:
            self.logger.error(f"Cache cleanup failed: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        try:
            with self._get_cursor() as cursor:
                # Basic counts
                cursor.execute("SELECT COUNT(*) FROM asin_cache")
                total_entries = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM asin_cache WHERE expires_at > ?",
                    (time.time(),),
                )
                active_entries = cursor.fetchone()[0]

                # Performance statistics
                total_operations = self._stats["hits"] + self._stats["misses"]
                hit_rate = (
                    (self._stats["hits"] / total_operations * 100)
                    if total_operations > 0
                    else 0.0
                )

                # Source distribution
                cursor.execute(
                    "SELECT source, COUNT(*) FROM asin_cache GROUP BY source"
                )
                source_distribution = dict(cursor.fetchall())

                # Top accessed entries
                cursor.execute(
                    """
                    SELECT cache_key, asin, access_count, source 
                    FROM asin_cache 
                    ORDER BY access_count DESC 
                    LIMIT 10
                """
                )
                top_entries = cursor.fetchall()

                # Database file size
                if self.cache_path.exists():
                    size_bytes = self.cache_path.stat().st_size
                    last_updated = datetime.fromtimestamp(
                        self.cache_path.stat().st_mtime
                    )
                else:
                    size_bytes = 0
                    last_updated = datetime.now()

                # Human readable size
                size_human = self._format_bytes(size_bytes)

                return {
                    "total_entries": total_entries,
                    "active_entries": active_entries,
                    "expired_entries": total_entries - active_entries,
                    "hit_rate": round(hit_rate, 2),
                    "hits": self._stats["hits"],
                    "misses": self._stats["misses"],
                    "writes": self._stats["writes"],
                    "cleanup_runs": self._stats["cleanup_runs"],
                    "migrated_entries": self._stats["migrated_entries"],
                    "size_bytes": size_bytes,
                    "size_human": size_human,
                    "last_updated": last_updated,
                    "source_distribution": source_distribution,
                    "top_entries": top_entries,
                    "ttl_days": self.ttl_days,
                }

        except sqlite3.Error as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e), "total_entries": 0, "hit_rate": 0.0}

    def clear(self):
        """Clear all cached entries."""
        try:
            with self._get_cursor() as cursor:
                cursor.execute("DELETE FROM asin_cache")
                cursor.execute("VACUUM")  # Reclaim space

            # Reset statistics
            self._stats = {key: 0 for key in self._stats}

            self.logger.info("Cleared all cache entries")

        except sqlite3.Error as e:
            self.logger.error(f"Failed to clear cache: {e}")

    def close(self):
        """Close database connections."""
        if hasattr(self._local, "connection"):
            self._local.connection.close()
            delattr(self._local, "connection")

    @staticmethod
    def _format_bytes(bytes_size: int) -> str:
        """Format bytes to human readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.close()


class JSONCacheManager:
    """
    Legacy JSON-based cache manager for backward compatibility.

    This class maintains the same interface as SQLiteCacheManager but uses
    the original JSON file format for environments where SQLite is not desired.
    """

    def __init__(self, cache_path: Path):
        """Initialize JSON cache manager."""
        self.cache_path = cache_path
        self.cache_data = {}
        self._cache_lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "writes": 0}
        self.logger = logging.getLogger(__name__)
        self._load_cache()

    def _load_cache(self):
        """Load cache from JSON file."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r") as f:
                    self.cache_data = json.load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load JSON cache: {e}")
                self.cache_data = {}
        else:
            self.cache_data = {}
            # Ensure cache directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _save_cache(self):
        """Save cache to JSON file."""
        try:
            with open(self.cache_path, "w") as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Failed to save JSON cache: {e}")

    def get_cached_asin(self, cache_key: str) -> Optional[str]:
        """Get cached ASIN for key."""
        with self._cache_lock:
            asin = self.cache_data.get(cache_key)
            if asin:
                self._stats["hits"] += 1
            else:
                self._stats["misses"] += 1
            return asin

    def cache_asin(
        self,
        cache_key: str,
        asin: str,
        source: str = "unknown",
        confidence_score: float = 1.0,
    ):
        """Cache an ASIN (ignores metadata in JSON version)."""
        with self._cache_lock:
            self.cache_data[cache_key] = asin
            self._stats["writes"] += 1
            self._save_cache()

    def get_stats(self) -> Dict[str, Any]:
        """Get basic cache statistics."""
        from datetime import datetime

        with self._cache_lock:
            total_entries = len(self.cache_data)
            total_operations = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                (self._stats["hits"] / total_operations * 100)
                if total_operations > 0
                else 0.0
            )

            # Calculate cache file size
            if self.cache_path.exists():
                size_bytes = self.cache_path.stat().st_size
                last_updated = datetime.fromtimestamp(self.cache_path.stat().st_mtime)
            else:
                size_bytes = 0
                last_updated = datetime.now()

            size_human = SQLiteCacheManager._format_bytes(size_bytes)

            return {
                "total_entries": total_entries,
                "active_entries": total_entries,  # No expiration in JSON version
                "expired_entries": 0,
                "hit_rate": round(hit_rate, 2),
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "writes": self._stats["writes"],
                "size_bytes": size_bytes,
                "size_human": size_human,
                "last_updated": last_updated,
                "backend": "json",
            }

    def clear(self):
        """Clear all cached entries."""
        with self._cache_lock:
            self.cache_data = {}
            self._stats = {key: 0 for key in self._stats}
            self._save_cache()

    def cleanup_expired(self) -> int:
        """No-op for JSON cache (no expiration support)."""
        return 0

    def close(self):
        """No-op for JSON cache (no connections to close)."""


def create_cache_manager(cache_path: Path, backend: str = "sqlite", **kwargs) -> Any:
    """
    Factory function to create appropriate cache manager.

    Args:
        cache_path: Path to cache file
        backend: 'sqlite' or 'json'
        **kwargs: Additional arguments for SQLiteCacheManager

    Returns:
        Cache manager instance
    """
    if backend.lower() == "sqlite":
        return SQLiteCacheManager(cache_path, **kwargs)
    elif backend.lower() == "json":
        return JSONCacheManager(cache_path)
    else:
        raise ValueError(f"Unknown cache backend: {backend}")
