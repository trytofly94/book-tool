# Transform Book Automation Scripts to CLI Tool

**Erstellt**: 2025-09-05
**Typ**: Feature
**Geschätzter Aufwand**: Groß
**Verwandtes Issue**: Direct user request - CLI tool transformation

## Kontext & Ziel

Transform the existing collection of Python scripts for book automation (downloading, ASIN lookup, Calibre integration, KFX conversion) into a proper system-wide CLI tool. The current scripts work well but lack proper packaging, distribution, and maintainability structure. The goal is to create a professional CLI tool that can be installed via pip or homebrew and follows software engineering best practices.

### Current State Analysis
- **Existing Scripts**: 8+ Python scripts with specialized functionality
- **Architecture**: Individual scripts with hardcoded paths and configurations  
- **Dependencies**: Calibre CLI, librarian CLI, Selenium, requests, BeautifulSoup4
- **Current Usage**: Manual execution of individual scripts or master shell script
- **Pain Points**: No unified interface, hardcoded configurations, manual installation

### Target State Vision
- **Unified CLI**: Single `calibre-books` command with subcommands
- **Proper Packaging**: Installable via `pip install calibre-books` 
- **Configuration**: External config files with sensible defaults
- **Testing**: Comprehensive test suite with CI/CD integration
- **Documentation**: Professional documentation and examples
- **Distribution**: PyPI package with optional homebrew formula

## Anforderungen

### Core Functionality Requirements
- [ ] Maintain all existing functionality from current scripts
- [ ] Unified CLI interface with intuitive command structure
- [ ] Configuration file support (YAML/TOML format)
- [ ] Proper logging with configurable levels
- [ ] Error handling with user-friendly messages
- [ ] Progress indicators for long-running operations

### Technical Requirements  
- [ ] Python 3.9+ compatibility
- [ ] Cross-platform support (macOS, Linux, Windows)
- [ ] Minimal external dependencies (only essential ones)
- [ ] Proper package structure following Python best practices
- [ ] Test coverage > 80%
- [ ] Type hints throughout codebase

### Distribution Requirements
- [ ] PyPI package for `pip install calibre-books`
- [ ] Optional homebrew formula for macOS
- [ ] Docker container option for isolated execution
- [ ] GitHub releases with proper versioning (semantic versioning)
- [ ] Installation verification command

### User Experience Requirements
- [ ] Intuitive command structure and help system
- [ ] Configuration wizard for first-time setup
- [ ] Comprehensive error messages with suggested solutions
- [ ] Progress bars for long operations
- [ ] Dry-run mode for all destructive operations

## Untersuchung & Analyse

### Existing Code Architecture Analysis

**Core Components Identified:**
1. **ASIN Management** (`calibre_asin_automation.py`, `enhanced_asin_lookup.py`)
   - Multi-source ASIN lookup using web scraping and APIs
   - Calibre database integration for metadata management
   - Caching system for performance optimization

2. **Book Download** (`auto_download_books.py`)
   - Integration with librarian CLI for automated downloads
   - Series detection and batch processing
   - File management and organization

3. **Format Conversion** (`parallel_kfx_converter.py`)
   - Parallel KFX conversion for Goodreads integration
   - Calibre plugin management and validation
   - Multi-threaded processing for efficiency

4. **Calibre Integration** (multiple `calibre_*.py` files)
   - Database management and metadata manipulation
   - CLI tool orchestration
   - Library management utilities

5. **Master Orchestration** (`book_automation_master.sh`)
   - Workflow coordination between components
   - User interface for script selection
   - Dependency validation

### Dependency Analysis
- **Critical External Dependencies**: Calibre CLI tools, Chrome browser, librarian CLI
- **Python Dependencies**: requests, beautifulsoup4, selenium, webdriver-manager
- **System Dependencies**: macOS/Linux paths, file system permissions

### Configuration Refactoring Needs
- **Hardcoded Paths**: `/Volumes/Entertainment/Bücher/Calibre-Ingest`, `/tmp/asin_cache.json`
- **File Formats**: Currently mobi-focused, needs format flexibility
- **Library Paths**: Currently assumes specific Calibre library structure
- **Cache Locations**: Temporary file handling needs improvement

## Implementierungsplan

### Phase 1: Project Structure & Packaging Foundation
- [ ] Create proper Python package structure with `src/` layout
- [ ] Set up `pyproject.toml` with modern Python packaging standards
- [ ] Configure build system (setuptools-scm for versioning)
- [ ] Create entry points for CLI commands
- [ ] Set up development environment (pre-commit hooks, etc.)

### Phase 2: CLI Interface Design & Implementation
- [ ] Design command hierarchy and interface (`calibre-books <command> <subcommand>`)
- [ ] Implement main CLI dispatcher with `click` or `argparse`
- [ ] Create subcommands for each major functionality area
- [ ] Add global options (config file, log level, dry-run mode)
- [ ] Implement help system and command documentation

### Phase 3: Configuration Management System
- [ ] Design configuration schema (YAML format recommended)
- [ ] Implement configuration loading with environment variable overrides
- [ ] Create configuration validation and error reporting
- [ ] Add configuration wizard for first-time setup
- [ ] Support for multiple configuration profiles

### Phase 4: Core Module Refactoring
- [ ] Extract business logic from existing scripts into modular classes
- [ ] Implement proper logging throughout all modules
- [ ] Add error handling with custom exception hierarchy
- [ ] Create data models for books, metadata, and configuration
- [ ] Implement plugin system for extensibility

### Phase 5: Testing Infrastructure
- [ ] Set up pytest testing framework with fixtures
- [ ] Create unit tests for all core business logic
- [ ] Add integration tests for CLI interface
- [ ] Mock external dependencies (Calibre, librarian, web services)
- [ ] Set up coverage reporting and quality gates

### Phase 6: Advanced Features & Polish
- [ ] Add progress indicators for long-running operations
- [ ] Implement dry-run mode for all destructive operations  
- [ ] Add shell completion (bash, zsh, fish)
- [ ] Create plugin system for custom ASIN sources
- [ ] Add configuration backup/restore functionality

### Phase 7: Documentation & Distribution
- [ ] Write comprehensive README with examples
- [ ] Create man pages for CLI commands
- [ ] Set up Sphinx documentation with API reference
- [ ] Prepare PyPI package for distribution
- [ ] Create homebrew formula (optional)

### Phase 8: Testing & Deployment
- [ ] End-to-end testing with real Calibre libraries
- [ ] Performance testing and optimization
- [ ] Security review of web scraping components
- [ ] Beta testing with actual users
- [ ] Final release preparation and documentation

## Detailed Architecture Design

### Proposed Package Structure
```
calibre-books/
├── src/
│   └── calibre_books/
│       ├── __init__.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── main.py           # Main CLI dispatcher
│       │   ├── download.py       # Download commands
│       │   ├── asin.py           # ASIN management commands  
│       │   ├── convert.py        # Format conversion commands
│       │   └── config.py         # Configuration commands
│       ├── core/
│       │   ├── __init__.py
│       │   ├── book.py           # Book data models
│       │   ├── calibre.py        # Calibre integration
│       │   ├── downloader.py     # Download functionality
│       │   ├── asin_lookup.py    # ASIN lookup service
│       │   └── converter.py      # Format conversion
│       ├── config/
│       │   ├── __init__.py
│       │   ├── manager.py        # Configuration management
│       │   └── schema.py         # Configuration validation
│       └── utils/
│           ├── __init__.py
│           ├── logging.py        # Logging setup
│           ├── progress.py       # Progress indicators
│           └── validation.py     # Input validation
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── cli/
│   ├── api/
│   └── examples/
├── scripts/
│   ├── install.sh
│   └── setup-dev.sh
├── pyproject.toml
├── README.md
├── CHANGELOG.md
└── LICENSE
```

### CLI Command Structure
```bash
# Main command groups
calibre-books download <options>          # Download books
calibre-books asin <subcommand>           # ASIN management  
calibre-books convert <options>           # Format conversion
calibre-books library <subcommand>        # Library management
calibre-books config <subcommand>         # Configuration

# Specific examples
calibre-books download --series "Stormlight Archive" --format mobi
calibre-books asin lookup --book "The Way of Kings"
calibre-books asin batch-update --library ~/Calibre-Library
calibre-books convert kfx --input-dir ./books --parallel 4
calibre-books library status --detailed
calibre-books config init --interactive
calibre-books config show --section downloads
```

### Configuration Schema Design
```yaml
# ~/.calibre-books/config.yml
download:
  default_format: mobi
  download_path: ~/Downloads/Books
  librarian_path: librarian
  
calibre:
  library_path: ~/Calibre-Library
  cli_path: auto  # auto-detect or specify path
  
asin_lookup:
  cache_path: ~/.calibre-books/asin_cache.json
  sources: [amazon, goodreads, openlibrary]
  rate_limit: 2.0  # seconds between requests
  
conversion:
  max_parallel: 4
  output_path: ~/Converted-Books
  kfx_plugin_required: true
  
logging:
  level: INFO
  file: ~/.calibre-books/logs/calibre-books.log
  format: detailed
```

### Plugin System Design
```python
# Plugin interface for custom ASIN sources
class ASINSource:
    def __init__(self, config: dict):
        pass
    
    def lookup(self, title: str, author: str) -> Optional[str]:
        """Return ASIN or None if not found"""
        pass
    
    def batch_lookup(self, books: List[Book]) -> Dict[str, str]:
        """Batch lookup for efficiency"""  
        pass
```

## Fortschrittsnotizen

**2025-09-05**: Initial comprehensive plan created based on analysis of existing codebase. Identified 8 major phases for transformation with clear deliverables and dependencies. Architecture design emphasizes modularity, testability, and user experience.

**Key Technical Decisions Made:**
- Use `click` for CLI framework (more intuitive than argparse for complex CLIs)
- YAML configuration format (more user-friendly than JSON/TOML)
- `src/` package layout for better isolation and testing
- Plugin system for extensibility
- Comprehensive logging and error handling strategy

**Risk Assessment:**
- **High**: External dependency on Calibre CLI tools and librarian CLI
- **Medium**: Web scraping components may break with site changes
- **Medium**: Cross-platform compatibility challenges
- **Low**: Python packaging and distribution complexity

**Next Steps Priority:**
1. Start with Phase 1 (Project Structure) as foundation
2. Implement basic CLI interface early for user feedback
3. Maintain backward compatibility during transition
4. Focus on core functionality before advanced features

## Ressourcen & Referenzen

### Technical Documentation
- [Python Packaging User Guide](https://packaging.python.org/)
- [Click Documentation](https://click.palletsprojects.com/)
- [pytest Documentation](https://docs.pytest.org/)
- [Calibre CLI Documentation](https://manual.calibre-ebook.com/generated/en/cli-index.html)

### Best Practices References
- [Python CLI Best Practices](https://github.com/knowsuchagency/python-cli-skeleton)
- [Modern Python Packaging](https://hynek.me/articles/python-app-deps-2018/)
- [CLI UX Guidelines](https://clig.dev/)

### Similar Projects for Inspiration
- [ebook-tools](https://github.com/na--/ebook-tools)
- [calibre-web](https://github.com/janeczku/calibre-web)
- [GoodReads CSV Parser](https://github.com/thundergnat/GoodReads-book-list-parser)

## Abschluss-Checkliste

### Phase 1 Complete (Project Foundation)
- [ ] Python package structure created
- [ ] pyproject.toml configured
- [ ] Development environment set up
- [ ] Basic CLI entry point working

### Phase 2 Complete (CLI Interface)
- [ ] Command hierarchy implemented  
- [ ] All major subcommands available
- [ ] Help system comprehensive
- [ ] Global options functional

### Phase 3 Complete (Configuration)
- [ ] Configuration schema defined
- [ ] Config file loading works
- [ ] Validation and error reporting
- [ ] Setup wizard functional

### Phase 4 Complete (Core Refactoring)
- [ ] All existing functionality migrated
- [ ] Proper logging throughout
- [ ] Error handling implemented
- [ ] Business logic extracted

### Phase 5 Complete (Testing)
- [ ] Unit test coverage > 80%
- [ ] Integration tests passing
- [ ] CI/CD pipeline configured
- [ ] Quality gates enforced

### Phase 6 Complete (Advanced Features)
- [ ] Progress indicators implemented
- [ ] Dry-run mode available
- [ ] Shell completion configured
- [ ] Plugin system working

### Phase 7 Complete (Documentation)
- [ ] README comprehensive
- [ ] CLI help complete
- [ ] API documentation generated
- [ ] Examples provided

### Phase 8 Complete (Release)
- [ ] PyPI package published
- [ ] Installation tested
- [ ] Performance validated
- [ ] User feedback incorporated

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-05