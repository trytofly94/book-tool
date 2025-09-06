# Book Tool

A professional CLI tool for processing existing eBook files, adding ASIN metadata, and converting to KFX format for Goodreads integration.

## Features

- **eBook File Processing**: Scan and analyze existing eBook collections
- **ASIN Management**: Automatic lookup and assignment of Amazon Standard Identification Numbers
- **Calibre Integration**: Seamless integration with Calibre database and metadata management
- **KFX Conversion**: Parallel conversion to KFX format for enhanced Goodreads integration
- **Multi-Source Lookup**: Enhanced metadata lookup using multiple sources including web scraping
- **Batch Processing**: Efficient parallel processing for large book collections

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
book-tool asin lookup --book "The Way of Kings" --author "Brandon Sanderson"
book-tool asin batch-update --library ~/Calibre-Library
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

## Development Roadmap

This project is being transformed into a proper CLI tool with:

- [ ] Package structure with `setup.py`/`pyproject.toml`
- [ ] Unified CLI interface with `argparse`
- [ ] External configuration files
- [ ] Comprehensive test suite
- [ ] pip-installable package
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