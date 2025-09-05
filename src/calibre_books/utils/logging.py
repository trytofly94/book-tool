"""
Logging setup and utilities for Calibre Books CLI.

This module provides centralized logging configuration with support for
different output formats, file logging, and Rich console integration.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    format_style: str = "detailed",
    quiet: bool = False,
) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        format_style: Format style ('simple' or 'detailed')
        quiet: If True, suppress console output except for errors
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Set up console logging with Rich
    if not quiet:
        console = Console()
        console_handler = RichHandler(
            console=console,
            show_path=level.upper() == "DEBUG",
            show_time=format_style == "detailed",
            rich_tracebacks=True,
            tracebacks_show_locals=level.upper() == "DEBUG",
        )
        
        if format_style == "simple":
            console_format = "%(message)s"
        else:
            console_format = "%(name)s: %(message)s"
        
        console_handler.setFormatter(logging.Formatter(console_format))
        console_handler.setLevel(numeric_level)
        root_logger.addHandler(console_handler)
    else:
        # Even in quiet mode, show errors on stderr
        error_handler = logging.StreamHandler(sys.stderr)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            logging.Formatter("[ERROR] %(name)s: %(message)s")
        )
        root_logger.addHandler(error_handler)
    
    # Set up file logging if requested
    if log_file:
        log_file = Path(log_file).expanduser().resolve()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Use rotating file handler to prevent huge log files
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        
        file_format = (
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(filename)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(logging.Formatter(file_format))
        file_handler.setLevel(logging.DEBUG)  # Always debug level for files
        root_logger.addHandler(file_handler)
    
    # Set specific logger levels to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("webdriver_manager").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    Mixin class to add logging capabilities to other classes.
    
    Usage:
        class MyClass(LoggerMixin):
            def __init__(self):
                super().__init__()
                self.logger.info("MyClass initialized")
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = None
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance for this class."""
        if self._logger is None:
            self._logger = get_logger(
                f"{self.__class__.__module__}.{self.__class__.__name__}"
            )
        return self._logger


def log_operation(operation_name: str):
    """
    Decorator to log the start and completion of operations.
    
    Args:
        operation_name: Human-readable name for the operation
        
    Usage:
        @log_operation("downloading book")
        def download_book(self, title):
            # ... implementation
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if hasattr(self, 'logger'):
                logger = self.logger
            else:
                logger = get_logger(func.__module__)
            
            logger.info(f"Starting {operation_name}...")
            try:
                result = func(self, *args, **kwargs)
                logger.info(f"Completed {operation_name} successfully")
                return result
            except Exception as e:
                logger.error(f"Failed {operation_name}: {e}")
                raise
        return wrapper
    return decorator