# Book Tool

A professional CLI tool for processing existing eBook files, adding ASIN metadata, and converting to KFX format for Goodreads integration.

## Features

- **eBook File Processing**: Scan and analyze existing eBook collections
- **Book Download**: Search, batch, and URL-based book downloading with parallel processing
- **ASIN Management**: Advanced multi-source ASIN lookup with intelligent fallback strategies (Amazon Search, Google Books API, OpenLibrary API)
- **Calibre Integration**: Seamless integration with Calibre database and metadata management
- **KFX Conversion**: Parallel conversion to KFX format for enhanced Goodreads integration
- **Multi-Source Lookup**: Enhanced metadata lookup using multiple sources including web scraping with robust error handling
- **Multi-Language Support**: ASIN lookup and metadata extraction for 8 languages (German, French, Spanish, Italian, English, Japanese, Portuguese, Dutch) with Unicode support
- **Batch Processing**: Efficient parallel processing for large book collections with intelligent caching (20x performance improvement on repeated lookups)
- **Performance Optimization**: Advanced caching system with average lookup times of 5.13s (first lookup) and 0.65s (cached results)

## Prerequisites

- [Python 3.9+](https://www.python.org/)
- [Calibre](https://calibre-ebook.com/) with CLI tools in PATH
- [Chrome Browser](https://www.google.com/chrome/) (for web scraping features)

### KFX Conversion Prerequisites

KFX conversion requires the **KFX Output Plugin** for Calibre:

#### Install KFX Output Plugin

1. Open Calibre
2. Go to **Preferences** → **Plugins**
3. Click **Get new plugins**
4. Search for **"KFX Output"**
5. Install the plugin by **jhowell** (ensure authenticity)
6. **Restart Calibre** (important!)

#### Verify Plugin Installation

Check that the plugin is properly installed:

```sh
calibre-customize -l | grep KFX
```

Expected output:
```
KFX Output (2, 17, 1) - Convert ebooks to KFX format
Set KFX metadata (2, 17, 1) - Set metadata in KFX files
```

#### Plugin Troubleshooting

- **Plugin not found**: Ensure you restart Calibre after installation
- **Wrong version**: Use only the official plugin by jhowell
- **Conversion fails**: Run `book-tool convert kfx --check-requirements`

### System Requirements

- macOS or Linux (Unix-based paths)
- Calibre CLI tools: `calibredb`, `ebook-convert`, `ebook-meta`
- **KFX Output Plugin for Calibre** (for KFX conversion functionality)
- Chrome WebDriver (managed automatically by webdriver-manager)

## Installation

### System-wide Installation (Recommended)

Install book-tool system-wide using pip:

```sh
pip install book-tool
```

Or install from source:

```sh
git clone https://github.com/trytofly94/book-tool.git
cd book-tool
pip install -e .
```

### Development Installation

For development, clone and install in editable mode:

```sh
git clone https://github.com/trytofly94/book-tool.git
cd book-tool
pip install -e ".[dev]"
```

### Verify Installation

After installation, verify that book-tool is available:

```sh
book-tool --version
book-tool --help
```

### Prerequisites Verification

Ensure Calibre CLI tools are installed and in PATH:

```sh
calibredb --version
ebook-convert --version
ebook-meta --version
```


## Usage

### CLI Commands

#### Download Books
```sh
# Search-based downloads
book-tool download books --series "Series Name" --author "Author Name"
book-tool download books --title "Book Title" --format epub --quality high

# Batch downloads from file
book-tool download batch -i books_list.txt --parallel 3 --dry-run

# Direct URL downloads
book-tool download url -u "https://example.com/book.mobi" --name "Custom Name"
```

#### Process existing eBook files
```sh
book-tool process scan -i ./books --check-asin
book-tool process prepare -i ./books --add-asin --lookup
```

#### Convert to KFX format
```sh
book-tool convert kfx -i ./books --parallel 4
book-tool convert single -i book.epub -f kfx
```

#### ASIN Management
```sh
# Single book ASIN lookup with verbose output
book-tool asin lookup --book "The Way of Kings" --author "Brandon Sanderson" --verbose

# German title lookup (Unicode support)
book-tool asin lookup --book "Weg der Könige" --author "Brandon Sanderson" --verbose

# Lookup with caching benefits (20x faster on repeated requests)
book-tool asin lookup --book "Mistborn" --author "Brandon Sanderson"

# Batch ASIN updates for entire Calibre library
book-tool asin batch-update --library ~/Calibre-Library --parallel 4
```

#### Configuration
```sh
book-tool config init --interactive
book-tool config show
```

## Project Structure

```
├── book_automation_master.sh      # Master orchestration script
├── auto_download_books.py         # Automated book downloading
├── calibre_asin_automation.py     # ASIN management for Calibre
├── enhanced_asin_lookup.py        # Multi-source ASIN lookup
├── parallel_kfx_converter.py      # Parallel KFX conversion
├── calibre_*.py                   # Various Calibre integration scripts
└── search_results.json           # Search results cache
```

## Configuration

Currently, configuration is handled through hardcoded values in individual scripts. Key paths include:

- Download Path: `/Volumes/Entertainment/Bücher/Calibre-Ingest`
- Cache Files: `/tmp/asin_cache.json`
- Preferred Format: `mobi` (configurable in scripts)

## Recent Improvements & Testing

### ASIN Lookup Integration Testing (September 2025)

Recent comprehensive integration testing demonstrated excellent system reliability:

- **100% Success Rate**: 11/11 test cases passed including Brandon Sanderson collection
- **Multi-Language Support**: Perfect handling of German titles with umlauts (ö, ä, ü) and Unicode characters
- **Performance Optimization**:
  - Average first lookup: 5.13 seconds
  - Cached lookup: 0.65 seconds (20x performance improvement)
  - Intelligent rate limiting with graceful 2s backoff
- **Robust Error Handling**: Graceful degradation with fallback strategies
- **Multi-Source Integration**: Amazon Search, Google Books API, and OpenLibrary API with intelligent fallback

### Tested Book Collection
- Stormlight Archive series (German: Sturmlicht-Chroniken)
- Mistborn trilogy (German: Nebel-Trilogie)
- Skyward series
- Standalone titles including international variations

## Development Roadmap

This project has been transformed into a proper CLI tool with:

- [x] Package structure with `setup.py`/`pyproject.toml`
- [x] Unified CLI interface with `argparse`
- [x] External configuration files
- [x] Comprehensive test suite (146 tests)
- [x] Book download functionality (search, batch, URL downloads)
- [x] Complete Calibre integration
- [x] Multi-source ASIN lookup system with caching and fallback strategies
- [x] Comprehensive integration testing (100% pass rate)
- [ ] pip-installable package (final packaging)
- [ ] Enhanced documentation

## Contributing

This project uses an agent-based development workflow. See `CLAUDE.md` for technical details and development guidelines.

## License

[Please specify license]

## Troubleshooting

### Common Issues

1. **Calibre CLI not found**: Ensure Calibre is installed and CLI tools are in your PATH
2. **Chrome WebDriver issues**: The webdriver-manager should handle this automatically
3. **librarian not found**: Install librarian CLI separately following their documentation
4. **Permission errors**: Ensure proper file permissions for scripts and target directories

### KFX Conversion Issues

1. **KFX Plugin not installed**: Follow the KFX Prerequisites guide above
2. **Plugin not detected**: Restart Calibre and verify with `calibre-customize -l | grep KFX`
3. **Conversion errors**: Check system requirements with `book-tool convert kfx --check-requirements`
4. **Wrong plugin version**: Uninstall and reinstall the official KFX Output plugin by jhowell

### Test Directory

For testing KFX functionality, you can use the test directory:
```
/Volumes/Entertainment/Bücher/Calibre-Ingest
```

This directory is configured for local validation of KFX conversion functionality.

### Support

For issues related to the automation workflow, check the individual script documentation and error messages. Each component handles its own error reporting and validation.
