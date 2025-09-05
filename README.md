# Calibre Book Automation CLI

A comprehensive command-line tool for automating book downloads, metadata management, and Goodreads integration through Calibre.

## Features

- **Automated Book Downloads**: Download complete book series using the librarian CLI
- **ASIN Management**: Automatic lookup and assignment of Amazon Standard Identification Numbers
- **Calibre Integration**: Seamless integration with Calibre database and metadata management
- **KFX Conversion**: Parallel conversion to KFX format for enhanced Goodreads integration
- **Multi-Source Lookup**: Enhanced metadata lookup using multiple sources including web scraping
- **Batch Processing**: Efficient parallel processing for large book collections

## Prerequisites

- [Python 3.9+](https://www.python.org/) 
- [Calibre](https://calibre-ebook.com/) with CLI tools in PATH
- [Chrome Browser](https://www.google.com/chrome/) (for web scraping features)
- [librarian CLI](https://github.com/librarian-cli/librarian) for book downloads

### System Requirements

- macOS or Linux (Unix-based paths)
- Calibre CLI tools: `calibredb`, `ebook-convert`, `ebook-meta`
- Chrome WebDriver (managed automatically by webdriver-manager)

## Installation

1. Clone the repository:
   ```sh
   git clone [URL]
   cd Calibre-Ingest
   ```

2. Install Python dependencies:
   ```sh
   pip install requests beautifulsoup4 selenium webdriver-manager
   ```

3. Verify Calibre installation:
   ```sh
   calibredb --version
   ebook-convert --version
   ```

4. Install librarian CLI (follow their installation guide)

## Usage

### Master Automation Script

Run the interactive master script for guided workflows:

```sh
./book_automation_master.sh
```

### Individual Components

#### Download Books
```sh
python3 auto_download_books.py
```

#### ASIN Management
```sh
python3 calibre_asin_automation.py
```

#### KFX Conversion
```sh
python3 parallel_kfx_converter.py
```

#### Enhanced ASIN Lookup
```sh
python3 enhanced_asin_lookup.py
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

### Support

For issues related to the automation workflow, check the individual script documentation and error messages. Each component handles its own error reporting and validation.