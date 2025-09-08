"""
File validator module for comprehensive eBook file validation.

This module provides orchestration for validating large collections of eBook files,
including progress tracking, caching, and batch processing capabilities.
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..utils.logging import LoggerMixin
from ..utils.validation import ValidationResult, ValidationStatus, validate_file_format


class ValidationCache:
    """
    Cache validation results to avoid re-validating unchanged files.

    Uses file modification time and size as cache keys.
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """
        Initialize validation cache.

        Args:
            cache_file: Optional path to cache file (defaults to temp directory)
        """
        if cache_file is None:
            cache_file = Path.home() / ".cache" / "book-tool" / "validation_cache.json"

        self.cache_file = cache_file
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()

    def _get_file_key(self, file_path: Path) -> str:
        """Generate cache key for file based on path, size, and mtime."""
        try:
            stat = file_path.stat()
            key_data = f"{file_path}:{stat.st_size}:{stat.st_mtime}"
            return hashlib.sha256(key_data.encode()).hexdigest()
        except OSError:
            # If we can't stat the file, use path only
            return hashlib.sha256(str(file_path).encode()).hexdigest()

    def _load_cache(self) -> None:
        """Load cache from file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._cache = {}

    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except OSError:
            pass  # Ignore cache save failures

    def get_cached_result(self, file_path: Path) -> Optional[ValidationResult]:
        """Get cached validation result for file."""
        key = self._get_file_key(file_path)
        cached_data = self._cache.get(key)

        if cached_data:
            try:
                # Reconstruct ValidationResult from cached data
                status = ValidationStatus(cached_data["status"])
                return ValidationResult(
                    status=status,
                    file_path=file_path,
                    format_detected=cached_data.get("format_detected"),
                    format_expected=cached_data.get("format_expected"),
                    errors=cached_data.get("errors", []),
                    warnings=cached_data.get("warnings", []),
                    details=cached_data.get("details", {}),
                )
            except (KeyError, ValueError):
                # Invalid cache entry, remove it
                del self._cache[key]

        return None

    def cache_result(self, result: ValidationResult) -> None:
        """Cache validation result."""
        key = self._get_file_key(result.file_path)
        self._cache[key] = {
            "status": result.status.value,
            "format_detected": result.format_detected,
            "format_expected": result.format_expected,
            "errors": result.errors,
            "warnings": result.warnings,
            "details": result.details,
        }
        self._save_cache()

    def clear_cache(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()


class FileValidator(LoggerMixin):
    """
    Orchestrates validation of eBook files with progress tracking and caching.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize file validator.

        Args:
            config: Configuration dictionary
        """
        super().__init__()
        self.config = config
        self.cache = ValidationCache()

    def validate_directory(
        self,
        directory: Path,
        recursive: bool = False,
        formats: Optional[List[str]] = None,
        use_cache: bool = True,
        progress_callback: Optional[Callable] = None,
        parallel: bool = False,
        max_workers: int = 4,
    ) -> List[ValidationResult]:
        """
        Validate all eBook files in a directory.

        Args:
            directory: Directory to scan and validate
            recursive: Whether to scan subdirectories
            formats: List of formats to include (e.g., ['epub', 'mobi'])
            use_cache: Whether to use cached validation results
            progress_callback: Optional progress callback function
            parallel: Whether to use parallel validation
            max_workers: Maximum number of worker threads for parallel validation

        Returns:
            List of ValidationResult objects
        """
        self.logger.info(
            f"Validating files in directory: {directory} (recursive: {recursive})"
        )

        # Discover eBook files
        files = self._discover_ebook_files(directory, recursive, formats)
        self.logger.info(f"Found {len(files)} eBook files to validate")

        if not files:
            return []

        # Validate files
        if parallel and len(files) > 1:
            return self._validate_files_parallel(
                files, use_cache, progress_callback, max_workers
            )
        else:
            return self._validate_files_sequential(files, use_cache, progress_callback)

    def validate_file(
        self, file_path: Path, use_cache: bool = True
    ) -> ValidationResult:
        """
        Validate a single eBook file.

        Args:
            file_path: Path to file to validate
            use_cache: Whether to use cached validation results

        Returns:
            ValidationResult object
        """
        # Check cache first
        if use_cache:
            cached_result = self.cache.get_cached_result(file_path)
            if cached_result:
                self.logger.debug(f"Using cached validation result for {file_path}")
                return cached_result

        # Perform validation
        self.logger.debug(f"Validating file: {file_path}")
        result = validate_file_format(file_path)

        # Cache result
        if use_cache:
            self.cache.cache_result(result)

        return result

    def _discover_ebook_files(
        self, directory: Path, recursive: bool, formats: Optional[List[str]]
    ) -> List[Path]:
        """Discover eBook files in directory."""
        # Supported extensions
        ebook_extensions = {
            ".mobi",
            ".epub",
            ".azw",
            ".azw3",
            ".pdf",
            ".txt",
            ".fb2",
            ".lit",
            ".pdb",
            ".rtf",
            ".docx",
            ".doc",
        }

        # Filter by format if specified
        if formats:
            format_extensions = {f".{fmt.lower()}" for fmt in formats}
            ebook_extensions = ebook_extensions.intersection(format_extensions)

        # Find files
        pattern = "**/*" if recursive else "*"
        all_files = directory.glob(pattern)

        ebook_files = []
        for file_path in all_files:
            if file_path.is_file() and file_path.suffix.lower() in ebook_extensions:
                ebook_files.append(file_path)

        return sorted(ebook_files)

    def _validate_files_sequential(
        self, files: List[Path], use_cache: bool, progress_callback: Optional[Callable]
    ) -> List[ValidationResult]:
        """Validate files sequentially."""
        results = []

        for i, file_path in enumerate(files):
            if progress_callback:
                progress_callback(i + 1, len(files))

            try:
                result = self.validate_file(file_path, use_cache)
                results.append(result)
            except Exception as e:
                self.logger.warning(f"Failed to validate {file_path}: {e}")
                # Create error result
                error_result = ValidationResult(
                    status=ValidationStatus.UNREADABLE,
                    file_path=file_path,
                    errors=[f"Validation failed: {e}"],
                )
                results.append(error_result)

        return results

    def _validate_files_parallel(
        self,
        files: List[Path],
        use_cache: bool,
        progress_callback: Optional[Callable],
        max_workers: int,
    ) -> List[ValidationResult]:
        """Validate files in parallel."""
        results = []
        completed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(self.validate_file, file_path, use_cache): file_path
                for file_path in files
            }

            # Process completed tasks
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                completed_count += 1

                if progress_callback:
                    progress_callback(completed_count, len(files))

                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self.logger.warning(f"Failed to validate {file_path}: {e}")
                    # Create error result
                    error_result = ValidationResult(
                        status=ValidationStatus.UNREADABLE,
                        file_path=file_path,
                        errors=[f"Validation failed: {e}"],
                    )
                    results.append(error_result)

        # Sort results by file path to ensure consistent ordering
        results.sort(key=lambda r: r.file_path)
        return results

    def generate_summary(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Generate validation summary statistics.

        Args:
            results: List of validation results

        Returns:
            Dictionary containing summary statistics
        """
        if not results:
            return {"total_files": 0, "valid_files": 0, "invalid_files": 0}

        # Count by status
        status_counts = {}
        for status in ValidationStatus:
            status_counts[status.value] = sum(1 for r in results if r.status == status)

        # Count by format
        format_counts = {}
        for result in results:
            fmt = result.format_detected or result.format_expected or "unknown"
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

        # Identify problem files
        invalid_files = [r for r in results if not r.is_valid]
        extension_mismatches = [r for r in results if r.has_extension_mismatch]

        summary = {
            "total_files": len(results),
            "valid_files": status_counts.get("valid", 0),
            "invalid_files": len(results) - status_counts.get("valid", 0),
            "status_counts": status_counts,
            "format_counts": format_counts,
            "extension_mismatches": len(extension_mismatches),
            "problem_files": [
                {
                    "file": str(r.file_path),
                    "status": r.status.value,
                    "errors": r.errors,
                    "warnings": r.warnings,
                }
                for r in invalid_files
            ],
        }

        return summary

    def save_results(
        self,
        results: List[ValidationResult],
        output_file: Path,
        include_details: bool = False,
    ) -> None:
        """
        Save validation results to JSON file.

        Args:
            results: List of validation results
            output_file: Path to output JSON file
            include_details: Whether to include detailed validation info
        """
        try:
            # Generate summary
            summary = self.generate_summary(results)

            # Prepare file results
            file_results = []
            for result in results:
                file_data = {
                    "file_path": str(result.file_path),
                    "status": result.status.value,
                    "format_expected": result.format_expected,
                    "format_detected": result.format_detected,
                    "is_valid": result.is_valid,
                    "has_extension_mismatch": result.has_extension_mismatch,
                    "errors": result.errors,
                    "warnings": result.warnings,
                }

                if include_details:
                    file_data["details"] = result.details

                file_results.append(file_data)

            # Create output data
            output_data = {"summary": summary, "validation_results": file_results}

            # Save to file
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Saved validation results to {output_file}")

        except Exception as e:
            self.logger.error(f"Failed to save validation results: {e}")
            raise

    def clear_cache(self) -> None:
        """Clear validation cache."""
        self.cache.clear_cache()
        self.logger.info("Validation cache cleared")
