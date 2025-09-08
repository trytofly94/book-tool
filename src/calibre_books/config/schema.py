"""
Configuration schema and validation for Calibre Books CLI.

This module defines the configuration schema and provides validation
functionality for configuration files.
"""

from typing import Dict, Any, List
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class DownloadConfig(BaseModel):
    """Download configuration schema."""

    default_format: str = Field(default="mobi", description="Default download format")
    download_path: str = Field(
        default="~/Downloads/Books", description="Download directory"
    )
    librarian_path: str = Field(
        default="librarian", description="Path to librarian CLI"
    )
    max_parallel: int = Field(
        default=1, ge=1, le=8, description="Max parallel downloads"
    )
    quality: str = Field(default="high", description="Download quality preference")
    search_timeout: int = Field(
        default=60, ge=10, le=300, description="Search timeout in seconds"
    )
    download_timeout: int = Field(
        default=300, ge=60, le=3600, description="Download timeout in seconds"
    )

    @field_validator("default_format")
    @classmethod
    def validate_format(cls, v):
        valid_formats = {"mobi", "epub", "pdf", "azw3"}
        if v.lower() not in valid_formats:
            raise ValueError(f"Invalid format: {v}. Must be one of: {valid_formats}")
        return v.lower()

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v):
        valid_qualities = {"high", "medium", "low"}
        if v.lower() not in valid_qualities:
            raise ValueError(f"Invalid quality: {v}. Must be one of: {valid_qualities}")
        return v.lower()

    @field_validator("download_path")
    @classmethod
    def expand_path(cls, v):
        return str(Path(v).expanduser())


class CalibreConfig(BaseModel):
    """Calibre configuration schema."""

    library_path: str = Field(
        default="~/Calibre-Library", description="Calibre library path"
    )
    cli_path: str = Field(default="auto", description="Calibre CLI tools path")

    @field_validator("library_path")
    @classmethod
    def expand_path(cls, v):
        return str(Path(v).expanduser())


class ASINLookupConfig(BaseModel):
    """ASIN lookup configuration schema."""

    cache_path: str = Field(
        default="~/.book-tool/cache/asin_cache.json", description="ASIN cache file path"
    )
    sources: List[str] = Field(
        default=["amazon", "goodreads", "openlibrary"],
        description="ASIN lookup sources",
    )
    rate_limit: float = Field(default=2.0, ge=0.1, description="Rate limit in seconds")

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, v):
        valid_sources = {"amazon", "goodreads", "openlibrary"}
        for source in v:
            if source not in valid_sources:
                raise ValueError(
                    f"Invalid source: {source}. Must be one of: {valid_sources}"
                )
        return v


class ConversionConfig(BaseModel):
    """Conversion configuration schema."""

    max_parallel: int = Field(
        default=4, ge=1, le=16, description="Max parallel processes"
    )
    output_path: str = Field(
        default="~/Converted-Books", description="Conversion output path"
    )
    kfx_plugin_required: bool = Field(default=True, description="Require KFX plugin")

    @field_validator("output_path")
    @classmethod
    def expand_path(cls, v):
        return str(Path(v).expanduser())


class LoggingConfig(BaseModel):
    """Logging configuration schema."""

    level: str = Field(default="INFO", description="Log level")
    file: str = Field(
        default="~/.book-tool/logs/book-tool.log", description="Log file path"
    )
    format: str = Field(default="detailed", description="Log format style")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v):
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of: {valid_levels}")
        return v.upper()

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        valid_formats = {"simple", "detailed"}
        if v.lower() not in valid_formats:
            raise ValueError(
                f"Invalid log format: {v}. Must be one of: {valid_formats}"
            )
        return v.lower()


class ConfigurationSchema(BaseModel):
    """Main configuration schema."""

    download: DownloadConfig = Field(default_factory=DownloadConfig)
    calibre: CalibreConfig = Field(default_factory=CalibreConfig)
    asin_lookup: ASINLookupConfig = Field(default_factory=ASINLookupConfig)
    conversion: ConversionConfig = Field(default_factory=ConversionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def validate_config(cls, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration data against schema.

        Args:
            config_data: Raw configuration data

        Returns:
            Validated configuration data

        Raises:
            ValueError: If validation fails
        """
        try:
            # Create schema instance to validate
            schema = cls(**config_data)
            return schema.model_dump()
        except Exception as e:
            raise ValueError(f"Configuration validation failed: {e}")

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """Get default configuration."""
        schema = cls()
        return schema.model_dump()

    @classmethod
    def get_minimal_config(cls) -> Dict[str, Any]:
        """Get minimal configuration with only essential settings."""
        return {
            "download": {
                "default_format": "mobi",
                "download_path": "~/Downloads/Books",
                "librarian_path": "librarian",
                "max_parallel": 1,
            },
            "calibre": {
                "library_path": "~/Calibre-Library",
            },
            "logging": {
                "level": "INFO",
            },
        }

    @classmethod
    def get_config_template(cls) -> str:
        """Get configuration template with comments."""
        return """# Calibre Books CLI Configuration
# Generated configuration template with default values

# Download settings
download:
  default_format: mobi          # Preferred download format (mobi, epub, pdf, azw3)
  download_path: ~/Downloads/Books  # Directory for downloaded books
  librarian_path: librarian     # Path to librarian CLI tool
  max_parallel: 1               # Maximum parallel downloads (1-8)
  quality: high                 # Download quality preference (high, medium, low)
  search_timeout: 60            # Search timeout in seconds (10-300)
  download_timeout: 300         # Download timeout in seconds (60-3600)

# Calibre integration settings  
calibre:
  library_path: ~/Calibre-Library   # Path to your Calibre library
  cli_path: auto                    # Path to Calibre CLI tools (auto for auto-detection)

# ASIN lookup settings
asin_lookup:
  cache_path: ~/.book-tool/cache/asin_cache.json  # ASIN cache file
  sources:                          # ASIN lookup sources
    - amazon
    - goodreads  
    - openlibrary
  rate_limit: 2.0                   # Rate limit between requests (seconds)

# Format conversion settings
conversion:
  max_parallel: 4                   # Maximum parallel conversion processes
  output_path: ~/Converted-Books    # Output directory for converted books
  kfx_plugin_required: true         # Require KFX plugin for conversions

# Logging settings
logging:
  level: INFO                       # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  file: ~/.book-tool/logs/book-tool.log  # Log file path
  format: detailed                  # Log format (simple, detailed)
"""
