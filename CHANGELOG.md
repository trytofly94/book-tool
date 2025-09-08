# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-09

### Added
- Initial release of book-tool CLI
- eBook file processing and scanning functionality
- ASIN lookup and validation with multi-source web scraping
- KFX format conversion with parallel processing
- Calibre database integration
- Configuration management with YAML support
- Rich console output with progress bars
- Comprehensive CLI interface with Click framework
- Support for multiple eBook formats (MOBI, EPUB, AZW3, PDF, etc.)
- Batch processing capabilities
- System requirements checking

### Features
- **Process Command**: Scan and prepare existing eBook collections
- **Convert Command**: Parallel KFX conversion for Goodreads integration
- **ASIN Command**: Lookup and batch update ASIN metadata
- **Config Command**: Interactive configuration management

### Requirements
- Python 3.9+
- Calibre CLI tools
- Chrome Browser (for web scraping)
- macOS or Linux (Unix-based paths)
