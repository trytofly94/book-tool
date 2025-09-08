"""
Exception classes for the Calibre Books CLI tool.

This module defines specific exception classes for different types of errors
that can occur during book downloading and processing operations.
"""


class DownloadError(Exception):
    """Base exception for download-related errors."""

    def __init__(self, message: str, title: str = None, author: str = None):
        """
        Initialize download error.

        Args:
            message: Error message
            title: Book title if applicable
            author: Book author if applicable
        """
        super().__init__(message)
        self.title = title
        self.author = author


class LibrarianError(DownloadError):
    """Exception raised when librarian CLI operations fail."""

    def __init__(
        self,
        message: str,
        command: str = None,
        returncode: int = None,
        stderr: str = None,
    ):
        """
        Initialize librarian error.

        Args:
            message: Error message
            command: The librarian command that failed
            returncode: Process return code
            stderr: Standard error output
        """
        super().__init__(message)
        self.command = command
        self.returncode = returncode
        self.stderr = stderr


class ValidationError(Exception):
    """Exception raised for validation errors in input or configuration."""

    def __init__(self, message: str, field: str = None, value: str = None):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field name that failed validation
            value: Invalid value
        """
        super().__init__(message)
        self.field = field
        self.value = value


class NetworkError(DownloadError):
    """Exception raised for network-related errors."""

    def __init__(self, message: str, url: str = None, timeout: int = None):
        """
        Initialize network error.

        Args:
            message: Error message
            url: URL that caused the error
            timeout: Timeout value if timeout occurred
        """
        super().__init__(message)
        self.url = url
        self.timeout = timeout


class FormatError(ValidationError):
    """Exception raised for file format and parsing errors."""

    def __init__(self, message: str, filename: str = None, line_number: int = None):
        """
        Initialize format error.

        Args:
            message: Error message
            filename: File that caused the error
            line_number: Line number where error occurred
        """
        super().__init__(message)
        self.filename = filename
        self.line_number = line_number


class ConfigurationError(ValidationError):
    """Exception raised for configuration errors."""

    def __init__(self, message: str, config_key: str = None, config_value: str = None):
        """
        Initialize configuration error.

        Args:
            message: Error message
            config_key: Configuration key that's invalid
            config_value: Invalid configuration value
        """
        super().__init__(message, field=config_key, value=config_value)
        self.config_key = config_key
        self.config_value = config_value
