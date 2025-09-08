"""
ASIN management module for eBook files.

This module handles ASIN lookup, validation, and metadata updates
for eBook files to prepare them for Goodreads integration.
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from ..core.book import Book, ASINLookupResult
from ..utils.logging import LoggerMixin
from ..utils.validation import validate_asin


class ASINManager(LoggerMixin):
    """
    Manages ASIN lookup and metadata updates for eBook files.

    Integrates with existing ASIN lookup services and handles
    updating eBook file metadata with ASIN information.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ASIN manager.

        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config
        self._lookup_service = None

    @property
    def lookup_service(self):
        """Lazy load the ASIN lookup service."""
        if self._lookup_service is None:
            try:
                # Import the existing enhanced ASIN lookup service
                import sys

                # Add parent directory to path to import existing scripts
                parent_dir = Path(__file__).parent.parent.parent
                sys.path.insert(0, str(parent_dir))

                from enhanced_asin_lookup import ASINLookupService

                self._lookup_service = ASINLookupService()
                self.logger.info("Enhanced ASIN lookup service initialized")

            except ImportError as e:
                self.logger.warning(f"Enhanced ASIN lookup not available: {e}")
                self._lookup_service = None

        return self._lookup_service

    def process_books(
        self,
        books: List[Book],
        lookup_online: bool = True,
        progress_callback: Optional[Callable] = None,
    ) -> List[ASINLookupResult]:
        """
        Process books to add ASIN metadata.

        Args:
            books: List of books to process
            lookup_online: Whether to perform online ASIN lookup
            progress_callback: Optional progress callback

        Returns:
            List of ASIN lookup results
        """
        self.logger.info(f"Processing {len(books)} books for ASIN metadata")

        results = []

        for i, book in enumerate(books):
            if progress_callback:
                progress_callback(i + 1, len(books))

            try:
                result = self._process_single_book(book, lookup_online)
                results.append(result)

            except Exception as e:
                self.logger.error(f"Failed to process {book.file_path}: {e}")
                results.append(ASINLookupResult(book=book, success=False, error=str(e)))

        successful = sum(1 for r in results if r.success)
        self.logger.info(
            f"ASIN processing complete: {successful}/{len(results)} successful"
        )

        return results

    def _process_single_book(self, book: Book, lookup_online: bool) -> ASINLookupResult:
        """
        Process a single book for ASIN metadata.

        Args:
            book: Book to process
            lookup_online: Whether to perform online lookup

        Returns:
            ASIN lookup result
        """
        self.logger.debug(
            f"Processing book: {book.metadata.title} by {book.metadata.author}"
        )

        # Skip if book already has ASIN
        if book.has_asin:
            self.logger.debug(f"Book already has ASIN: {book.metadata.asin}")
            return ASINLookupResult(
                book=book, success=True, asin=book.metadata.asin, source="existing"
            )

        asin = None
        source = None

        if lookup_online and self.lookup_service:
            # Perform online ASIN lookup
            asin = self.lookup_service.lookup_multiple_sources(
                isbn=book.metadata.isbn,
                title=book.metadata.title,
                author=book.metadata.author,
            )

            if asin:
                source = "online_lookup"
                self.logger.info(
                    f"Found ASIN online: {asin} for '{book.metadata.title}'"
                )

        if not asin:
            return ASINLookupResult(book=book, success=False, error="No ASIN found")

        # Update file metadata with ASIN
        try:
            self._update_file_asin(book.file_path, asin)

            # Update book object
            book.metadata.asin = asin

            return ASINLookupResult(book=book, success=True, asin=asin, source=source)

        except Exception as e:
            return ASINLookupResult(
                book=book, success=False, asin=asin, error=f"Failed to update file: {e}"
            )

    def _update_file_asin(self, file_path: Path, asin: str) -> None:
        """
        Update eBook file with ASIN metadata using ebook-meta.

        Args:
            file_path: Path to eBook file
            asin: ASIN to add
        """
        if not validate_asin(asin):
            raise ValueError(f"Invalid ASIN format: {asin}")

        try:
            # Use Calibre's ebook-meta tool to add ASIN identifier
            cmd = ["ebook-meta", str(file_path), "--identifier", f"amazon:{asin}"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                raise RuntimeError(f"ebook-meta failed: {result.stderr}")

            self.logger.debug(f"Successfully added ASIN {asin} to {file_path}")

        except subprocess.TimeoutExpired:
            raise RuntimeError("ebook-meta command timed out")
        except FileNotFoundError:
            raise RuntimeError("ebook-meta not found - Calibre not installed?")

    def verify_asin(self, asin: str) -> bool:
        """
        Verify that an ASIN exists on Amazon.

        Args:
            asin: ASIN to verify

        Returns:
            True if ASIN exists, False otherwise
        """
        if not validate_asin(asin):
            return False

        try:
            import requests

            # Simple check - try to access Amazon product page
            url = f"https://www.amazon.com/dp/{asin}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }

            response = requests.head(
                url, headers=headers, timeout=10, allow_redirects=True
            )

            # Amazon returns 200 for valid ASINs, 404 for invalid ones
            return response.status_code == 200

        except Exception as e:
            self.logger.warning(f"Failed to verify ASIN {asin}: {e}")
            return False

    def get_asin_from_file(self, file_path: Path) -> Optional[str]:
        """
        Extract ASIN from eBook file metadata.

        Args:
            file_path: Path to eBook file

        Returns:
            ASIN if found, None otherwise
        """
        try:
            result = subprocess.run(
                ["ebook-meta", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Parse identifiers from output
                for line in result.stdout.split("\n"):
                    if "Identifiers" in line:
                        identifiers_str = line.split(":", 1)[1].strip()
                        for identifier in identifiers_str.split(","):
                            if ":" in identifier:
                                key, value = identifier.strip().split(":", 1)
                                if key.lower() == "amazon":
                                    asin = value.strip()
                                    if validate_asin(asin):
                                        return asin

        except Exception as e:
            self.logger.debug(f"Failed to extract ASIN from {file_path}: {e}")

        return None

    def remove_asin_from_file(self, file_path: Path) -> bool:
        """
        Remove ASIN identifier from eBook file.

        Args:
            file_path: Path to eBook file

        Returns:
            True if successful, False otherwise
        """
        try:
            # First, get current metadata
            result = subprocess.run(
                ["ebook-meta", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return False

            # Parse current identifiers and remove amazon one
            current_identifiers = []
            for line in result.stdout.split("\n"):
                if "Identifiers" in line:
                    identifiers_str = line.split(":", 1)[1].strip()
                    for identifier in identifiers_str.split(","):
                        if ":" in identifier:
                            key, value = identifier.strip().split(":", 1)
                            if key.lower() != "amazon":
                                current_identifiers.append(f"{key}:{value}")

            # Update file with remaining identifiers
            if current_identifiers:
                cmd = [
                    "ebook-meta",
                    str(file_path),
                    "--identifier",
                ] + current_identifiers
            else:
                # If no other identifiers, just clear all
                cmd = ["ebook-meta", str(file_path), "--identifier", ""]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            return result.returncode == 0

        except Exception as e:
            self.logger.error(f"Failed to remove ASIN from {file_path}: {e}")
            return False
