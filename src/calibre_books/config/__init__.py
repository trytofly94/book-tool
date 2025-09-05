"""
Configuration management package for Calibre Books CLI.

This package provides configuration loading, validation, and management
functionality including profile support and schema validation.
"""

from .manager import ConfigManager
from .schema import ConfigurationSchema

__all__ = [
    "ConfigManager",
    "ConfigurationSchema",
]