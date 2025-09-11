"""
Conversion submodule for specialized format conversions.

This module contains specialized converters that extend or wrap
the base FormatConverter functionality for specific use cases.
"""

from .kfx import KFXConverter

__all__ = ["KFXConverter"]
