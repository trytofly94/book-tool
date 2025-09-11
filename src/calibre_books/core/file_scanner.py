"""
File scanner module for discovering and analyzing eBook files.

This module provides functionality for scanning directories to find eBook files,
extracting metadata, and checking for ASIN presence.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from ..core.book import Book, BookMetadata, BookFormat
from ..utils.logging import LoggerMixin
from ..utils.validation import validate_asin


class FileScanner(LoggerMixin):
    """
    Scans directories for eBook files and extracts metadata.

    Supports various eBook formats and can check for existing ASIN metadata.
    """

    # Supported eBook formats
    SUPPORTED_FORMATS = {
        ".mobi": BookFormat.MOBI,
        ".epub": BookFormat.EPUB,
        ".azw": BookFormat.AZW,
        ".azw3": BookFormat.AZW3,
        ".pdf": BookFormat.PDF,
        ".txt": BookFormat.TXT,
        ".fb2": BookFormat.FB2,
        ".lit": BookFormat.LIT,
        ".pdb": BookFormat.PDB,
        ".rtf": BookFormat.RTF,
    }

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize file scanner.

        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = False,
        formats: Optional[List[str]] = None,
        check_metadata: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> List[Book]:
        """
        Scan directory for eBook files.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            formats: List of formats to include (e.g., ['mobi', 'epub'])
            check_metadata: Whether to extract metadata from files
            progress_callback: Optional progress callback function

        Returns:
            List of discovered Book objects
        """
        self.logger.info(f"Scanning directory: {directory} (recursive: {recursive})")

        # Normalize format filter
        format_filter = None
        if formats:
            format_filter = [f.lower().lstrip(".") for f in formats]

        books = []

        # Get file pattern
        pattern = "**/*" if recursive else "*"

        # Find all files
        all_files = list(directory.glob(pattern))
        ebook_files = [
            f
            for f in all_files
            if f.is_file() and self._is_ebook_file(f, format_filter)
        ]

        self.logger.info(f"Found {len(ebook_files)} eBook files")

        for i, file_path in enumerate(ebook_files):
            if progress_callback:
                progress_callback(i + 1, len(ebook_files))

            try:
                book = self._create_book_from_file(file_path, check_metadata)
                if book:
                    books.append(book)
            except Exception as e:
                self.logger.warning(f"Failed to process {file_path}: {e}")
                continue

        self.logger.info(f"Successfully processed {len(books)} books")
        return books

    def _is_ebook_file(
        self, file_path: Path, format_filter: Optional[List[str]] = None
    ) -> bool:
        """Check if file is a supported eBook format."""
        suffix = file_path.suffix.lower()

        if suffix not in self.SUPPORTED_FORMATS:
            return False

        if format_filter:
            format_name = suffix.lstrip(".")
            return format_name in format_filter

        return True

    def _create_book_from_file(
        self, file_path: Path, extract_metadata: bool = False
    ) -> Optional[Book]:
        """
        Create Book object from file path.

        Args:
            file_path: Path to eBook file
            extract_metadata: Whether to extract metadata from file

        Returns:
            Book object or None if failed
        """
        try:
            # Determine format
            suffix = file_path.suffix.lower()
            book_format = self.SUPPORTED_FORMATS.get(suffix)

            if not book_format:
                return None

            # Create basic metadata from filename
            metadata = self._extract_metadata_from_filename(file_path.name)
            # Set the format and file size in metadata
            metadata.format = book_format
            metadata.file_size = file_path.stat().st_size

            # Extract metadata from file if requested
            if extract_metadata:
                file_metadata = self._extract_metadata_from_file(file_path)
                if file_metadata:
                    # Merge file metadata with filename metadata
                    metadata = self._merge_metadata(metadata, file_metadata)

            # Create book object
            book = Book(
                metadata=metadata,
                file_path=file_path,
            )

            return book

        except Exception as e:
            self.logger.error(f"Failed to create book from {file_path}: {e}")
            return None

    def _extract_metadata_from_filename(self, filename: str) -> BookMetadata:
        """
        Extract basic metadata from filename.

        Tries to parse author and title from common filename patterns:
        - "Author - Title"
        - "Title by Author"
        - "author_title" (underscore pattern)
        """
        # Remove extension
        name_without_ext = Path(filename).stem

        # Try common patterns like "Author - Title" or "Title by Author"
        if " - " in name_without_ext:
            parts = name_without_ext.split(" - ", 1)
            if len(parts) == 2:
                return BookMetadata(title=parts[1].strip(), author=parts[0].strip())
        elif " by " in name_without_ext.lower():
            parts = name_without_ext.split(" by ", 1)
            if len(parts) == 2:
                return BookMetadata(title=parts[0].strip(), author=parts[1].strip())
        elif "_" in name_without_ext:
            # Handle underscore patterns like "author_title" or "author_series#_title"
            parts = name_without_ext.split("_", 1)
            if len(parts) == 2:
                author_part = parts[0].strip()
                title_part = parts[1].strip()

                # Expand known author abbreviations
                expanded_author = self._expand_author_name(author_part)

                # Clean up title part (replace underscores with spaces, handle special cases)
                cleaned_title = self._clean_title(title_part)

                return BookMetadata(title=cleaned_title, author=expanded_author)

        # Default: use filename as title
        return BookMetadata(title=name_without_ext, author="Unknown")

    def _expand_author_name(self, author_short: str) -> str:
        """
        Expand author abbreviations to full names.

        Args:
            author_short: Short author name (e.g., 'sanderson')

        Returns:
            Full author name or original if no mapping found
        """
        # Known author name mappings
        author_mappings = {
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

        # Return mapped name or capitalize original
        mapped_name = author_mappings.get(author_short.lower())
        if mapped_name:
            return mapped_name
        else:
            # Capitalize each word in the original
            return " ".join(
                word.capitalize() for word in author_short.replace("_", " ").split()
            )

    def _clean_title(self, title_raw: str) -> str:
        """
        Clean up title from filename patterns.

        Args:
            title_raw: Raw title from filename

        Returns:
            Cleaned and formatted title
        """
        # Replace underscores with spaces
        title = title_raw.replace("_", " ")

        # Handle special patterns like "mistborn1" -> "Mistborn 1"
        # Look for number patterns
        import re

        # Pattern: word+number -> "word number"
        title = re.sub(r"([a-zA-Z])(\d+)", r"\1 \2", title)

        # Pattern: number+word -> "number word"
        title = re.sub(r"(\d+)([a-zA-Z])", r"\1 \2", title)

        # Handle hyphens - keep them but ensure proper spacing
        title = re.sub(r"\s*-\s*", " - ", title)

        # Capitalize first letter of each major word
        # Split by spaces and hyphens for proper capitalization
        words = []
        for part in title.split():
            if "-" in part:
                # Handle hyphenated words
                hyphen_parts = part.split("-")
                capitalized_parts = [p.capitalize() if p else "" for p in hyphen_parts]
                words.append("-".join(capitalized_parts))
            else:
                # Regular word capitalization
                words.append(part.capitalize())

        return " ".join(words)

    def _extract_metadata_from_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from eBook file using ebook-meta.

        This requires Calibre to be installed.
        """
        try:
            import subprocess

            # Use Calibre's ebook-meta tool
            result = subprocess.run(
                ["ebook-meta", str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return self._parse_ebook_meta_output(result.stdout)
            else:
                self.logger.debug(f"ebook-meta failed for {file_path}: {result.stderr}")
                return None

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.debug(f"ebook-meta not available or timed out: {e}")
            return None
        except Exception as e:
            self.logger.warning(f"Failed to extract metadata from {file_path}: {e}")
            return None

    def _parse_ebook_meta_output(self, output: str) -> Dict[str, Any]:
        """Parse output from ebook-meta command."""
        metadata = {}

        for line in output.split("\n"):
            if ":" in line and not line.startswith(" "):
                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                # Map common fields
                if key == "title":
                    metadata["title"] = value
                elif key == "author(s)":
                    metadata["author"] = value
                elif key == "identifiers":
                    # Parse identifiers like "isbn:123456, amazon:B123456"
                    identifiers = {}
                    for identifier in value.split(","):
                        if ":" in identifier:
                            id_type, id_value = identifier.strip().split(":", 1)
                            identifiers[id_type.strip()] = id_value.strip()
                    metadata["identifiers"] = identifiers
                elif key == "published":
                    metadata["publication_year"] = value
                elif key == "publisher":
                    metadata["publisher"] = value
                elif key == "language":
                    metadata["language"] = value
                elif key == "rating":
                    try:
                        metadata["rating"] = float(value.split("/")[0])
                    except (ValueError, IndexError):
                        pass

        return metadata

    def _merge_metadata(
        self, filename_meta: BookMetadata, file_meta: Dict[str, Any]
    ) -> BookMetadata:
        """Merge filename metadata with file metadata, preferring file metadata."""
        # Start with filename metadata
        merged_data = filename_meta.model_dump()

        # Override with file metadata where available
        if "title" in file_meta and file_meta["title"]:
            merged_data["title"] = file_meta["title"]
        if "author" in file_meta and file_meta["author"]:
            merged_data["author"] = file_meta["author"]
        if "publication_year" in file_meta:
            merged_data["publication_year"] = file_meta["publication_year"]
        if "publisher" in file_meta:
            merged_data["publisher"] = file_meta["publisher"]
        if "language" in file_meta:
            merged_data["language"] = file_meta["language"]
        if "rating" in file_meta:
            merged_data["rating"] = file_meta["rating"]

        # Handle identifiers
        if "identifiers" in file_meta:
            identifiers = file_meta["identifiers"]
            if "isbn" in identifiers:
                merged_data["isbn"] = identifiers["isbn"]
            if "amazon" in identifiers:
                asin = identifiers["amazon"]
                if validate_asin(asin):
                    merged_data["asin"] = asin

        return BookMetadata(**merged_data)

    def save_results(self, books: List[Book], output_file: Path) -> None:
        """Save scan results to JSON file."""
        try:
            results = []
            for book in books:
                results.append(
                    {
                        "file_path": str(book.file_path),
                        "title": book.metadata.title,
                        "author": book.metadata.author,
                        "format": book.format.value,
                        "file_size": book.file_size,
                        "has_asin": book.has_asin,
                        "asin": book.metadata.asin,
                        "isbn": book.metadata.isbn,
                        "publication_year": book.metadata.publication_year,
                        "publisher": book.metadata.publisher,
                        "language": book.metadata.language,
                        "rating": book.metadata.rating,
                    }
                )

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    {"total_files": len(books), "books": results},
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            self.logger.info(f"Saved {len(books)} book records to {output_file}")

        except Exception as e:
            self.logger.error(f"Failed to save results to {output_file}: {e}")
            raise
