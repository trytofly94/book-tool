# Implement Core Conversion Functionality

**Erstellt**: 2025-09-07
**Typ**: Feature Implementation
**Geschätzter Aufwand**: Groß
**Verwandtes Issue**: Development Roadmap - Core Functionality Gap

## Kontext & Ziel

The book-tool project has established a solid CLI foundation with comprehensive testing infrastructure, but the core conversion functionality remains incomplete. The `FormatConverter` class in `src/calibre_books/core/converter.py` contains multiple TODO placeholders instead of actual implementation. This represents a critical gap between the well-designed CLI interface and the actual functionality users expect.

### Current State Analysis

**✅ Completed Infrastructure:**
- CLI tool framework with proper command structure
- Configuration management system with YAML support
- Test infrastructure with 146 passing tests (100% pass rate)
- KFX plugin validation functionality
- ASIN lookup and metadata management
- Calibre database integration
- Professional package structure with pyproject.toml

**❌ Missing Core Functionality:**
- `convert_single()` - Single file conversion (TODO placeholder)
- `convert_batch()` - Batch file conversion (TODO placeholder) 
- `convert_kfx_batch()` - KFX-specific batch conversion (TODO placeholder)
- `find_convertible_files()` - File discovery logic (TODO placeholder)
- `get_supported_formats()` - Dynamic format detection (static placeholder)

**🎯 Legacy Resources Available:**
- `parallel_kfx_converter.py` - Working parallel conversion implementation
- `calibre_asin_automation.py` - Metadata management patterns
- `book_automation_master.sh` - Integration orchestration patterns

### Problem Analysis

The CLI presents users with conversion commands that fail because the underlying functionality is not implemented:

```bash
$ book-tool convert kfx --input-dir ./books --parallel 4
# CLI accepts command but FormatConverter.convert_kfx_batch() returns empty list

$ book-tool convert single -i book.epub -f kfx  
# CLI accepts command but FormatConverter.convert_single() returns failure result
```

This creates a poor user experience and prevents the tool from fulfilling its primary purpose.

## Anforderungen

### Functional Requirements
- [ ] Single file conversion using Calibre's `ebook-convert` command
- [ ] Batch conversion with configurable parallelization (2-8 workers)  
- [ ] KFX-specific conversion with proper plugin validation
- [ ] File discovery with format filtering and recursive scanning
- [ ] Dynamic format detection from Calibre capabilities
- [ ] Progress reporting for long-running conversion operations
- [ ] Comprehensive error handling and recovery
- [ ] Metadata preservation during conversion

### Technical Requirements  
- [ ] Integration with existing ConfigManager for settings
- [ ] Proper logging using the established LoggerMixin pattern
- [ ] Type hints and dataclass usage following project conventions
- [ ] Exception handling with meaningful error messages
- [ ] Support for dry-run mode from CLI options
- [ ] Thread-safe operations for parallel processing
- [ ] Resource cleanup and proper subprocess management

### Quality Requirements
- [ ] Comprehensive unit tests for all conversion methods
- [ ] Integration tests with mock Calibre commands
- [ ] Performance testing for batch operations
- [ ] Error condition testing (missing files, invalid formats, etc.)
- [ ] Documentation strings following project style
- [ ] Code style compliance with ruff configuration

## Untersuchung & Analyse

### Prior Art Analysis

**Legacy Implementation Insights:**
1. **`parallel_kfx_converter.py`** - Contains working parallel conversion logic:
   - Uses `concurrent.futures.ThreadPoolExecutor` for parallelization
   - Implements proper KFX plugin validation
   - Handles conversion results and error reporting
   - Uses `subprocess.run()` with `ebook-convert` command

2. **`calibre_asin_automation.py`** - Shows metadata management patterns:
   - Database interaction patterns with `calibredb` commands
   - Error handling for missing books and metadata
   - Batch processing with progress reporting

3. **Current CLI Integration** - Shows expected interfaces:
   - ConfigManager integration for settings
   - Progress callbacks for user feedback
   - File path handling with pathlib.Path
   - Error result objects with detailed information

### Technical Architecture Analysis

**Current FormatConverter Design:**
```python
class FormatConverter(LoggerMixin):
    def __init__(self, config_manager: 'ConfigManager')
    # ✅ Good: Uses ConfigManager and LoggerMixin
    # ✅ Good: Proper typing with TYPE_CHECKING
    # ❌ Missing: Actual implementation methods
```

**Required Integration Points:**
1. **CLI Integration:** Convert commands must call FormatConverter methods
2. **Configuration:** Conversion settings from user config and CLI options
3. **Progress Reporting:** Progress callbacks for CLI progress bars
4. **Error Handling:** ConversionResult objects for success/failure reporting
5. **Testing:** Mock subprocess calls for reliable testing

### Implementation Strategy Analysis

**Approach 1: Port Legacy Code** (Selected)
- **Pros:** Working code exists, proven functionality
- **Cons:** Requires refactoring to match new architecture
- **Assessment:** Best approach - leverages existing working code

**Approach 2: Rewrite from Scratch** 
- **Pros:** Clean implementation matching current architecture
- **Cons:** Higher risk, longer development time
- **Assessment:** Unnecessary - working code available

**Approach 3: Gradual Implementation**
- **Pros:** Lower risk, incremental progress
- **Cons:** Longer time to complete functionality
- **Assessment:** Good for complex features, but conversion is well-understood

## Implementierungsplan

### Phase 1: Core Single File Conversion

#### Step 1: Implement `convert_single()` Method
- [ ] Extract conversion logic from `parallel_kfx_converter.py`
- [ ] Adapt to use ConfigManager settings instead of hardcoded values
- [ ] Implement subprocess call to `ebook-convert` with proper error handling
- [ ] Create ConversionResult objects with success/failure information
- [ ] Add comprehensive logging using LoggerMixin
- [ ] Handle metadata preservation options
- [ ] Support dry-run mode for testing

#### Step 2: Implement Format Detection
- [ ] Replace static `get_supported_formats()` with dynamic detection
- [ ] Query Calibre's supported formats using `ebook-convert --help`
- [ ] Parse format lists into structured Format objects
- [ ] Cache format information for performance
- [ ] Handle Calibre version differences gracefully

#### Step 3: Implement File Discovery
- [ ] Implement `find_convertible_files()` with recursive scanning
- [ ] Support format filtering and extension matching  
- [ ] Handle symlinks and special files appropriately
- [ ] Provide progress reporting for large directory scans
- [ ] Return sorted results for predictable behavior

### Phase 2: Batch Conversion Implementation

#### Step 4: Implement `convert_batch()` Method  
- [ ] Create thread pool for parallel processing
- [ ] Implement work queue with proper task distribution
- [ ] Add progress reporting with completion callbacks
- [ ] Handle partial failures gracefully
- [ ] Implement result aggregation and reporting
- [ ] Support cancellation and cleanup

#### Step 5: Implement `convert_kfx_batch()` Method
- [ ] Port specialized KFX logic from legacy converter
- [ ] Add KFX plugin validation before batch processing
- [ ] Handle KFX-specific conversion options and quality settings
- [ ] Implement proper error handling for plugin issues
- [ ] Support KFX-specific metadata preservation

### Phase 3: Integration and Testing

#### Step 6: CLI Integration Testing
- [ ] Test conversion commands with actual files in test directory
- [ ] Verify configuration flow from CLI to converter
- [ ] Test progress reporting and user feedback
- [ ] Validate error handling and user-friendly messages
- [ ] Test dry-run mode functionality

#### Step 7: Comprehensive Unit Testing
- [ ] Create unit tests for all conversion methods
- [ ] Mock subprocess calls for reliable testing
- [ ] Test error conditions and edge cases
- [ ] Test configuration handling and defaults
- [ ] Test parallel processing and thread safety
- [ ] Add performance benchmarks for batch operations

#### Step 8: Integration Testing
- [ ] Create integration tests with real Calibre installation
- [ ] Test with sample books in multiple formats
- [ ] Validate KFX conversion with actual plugin
- [ ] Test large batch operations with monitoring
- [ ] Verify metadata preservation end-to-end

### Phase 4: Documentation and Polish

#### Step 9: Documentation Updates
- [ ] Update README with actual conversion examples
- [ ] Document supported formats and conversion options
- [ ] Add troubleshooting guide for common conversion issues
- [ ] Create migration guide from legacy scripts
- [ ] Update CLI help text with accurate information

#### Step 10: Performance Optimization
- [ ] Profile conversion operations for bottlenecks
- [ ] Optimize file discovery for large directories
- [ ] Implement intelligent parallelization based on system resources
- [ ] Add conversion caching for duplicate operations
- [ ] Optimize memory usage for large batch operations

## Detailed Implementation Specifications

### Single File Conversion Architecture

```python
def convert_single(
    self,
    input_file: Path,
    output_file: Optional[Path] = None,
    output_format: str = "epub",
    quality: str = "high",
    include_cover: bool = True,
    preserve_metadata: bool = True,
    progress_callback=None,
) -> ConversionResult:
    """Convert a single book file to another format."""
    
    # 1. Validate input file exists and is readable
    # 2. Determine output file path if not specified
    # 3. Build ebook-convert command with options
    # 4. Execute subprocess with progress monitoring
    # 5. Handle conversion errors and subprocess failures
    # 6. Validate output file was created successfully
    # 7. Return ConversionResult with details
```

### Batch Conversion Architecture

```python
def convert_batch(
    self,
    files: List[Path],
    output_dir: Optional[Path] = None,
    output_format: str = "epub",
    parallel: int = 2,
    progress_callback=None,
) -> List[ConversionResult]:
    """Convert multiple files in batch with parallelization."""
    
    # 1. Validate all input files and output directory
    # 2. Create ThreadPoolExecutor with configured workers
    # 3. Submit conversion tasks with progress tracking
    # 4. Handle partial failures and continue processing
    # 5. Aggregate results and provide summary
    # 6. Clean up resources and temporary files
```

### Configuration Integration

```yaml
# Expected configuration structure
conversion:
  output_path: "~/Converted-Books"
  max_parallel: 4
  default_quality: "high"
  preserve_metadata: true
  kfx_plugin_required: true
  supported_formats_cache_ttl: 3600
```

### Error Handling Strategy

1. **Input Validation Errors**: Clear messages about missing files or invalid formats
2. **Calibre Command Errors**: Parse stderr output for specific error types
3. **Plugin Missing Errors**: Helpful guidance for KFX plugin installation
4. **Disk Space Errors**: Check available space before large conversions
5. **Permission Errors**: Clear messages about file access issues

## Fortschrittsnotizen

**2025-09-07**: Initial analysis completed. Identified that core conversion functionality is completely missing despite solid CLI foundation. Legacy code exists with working implementations that can be adapted to the new architecture.

**Key Findings**:
- CLI foundation is excellent with 100% test pass rate
- FormatConverter class exists but all methods are TODO placeholders
- Legacy `parallel_kfx_converter.py` contains working conversion logic
- Test infrastructure is ready for comprehensive testing
- Configuration system is ready for conversion settings

**Risk Assessment**:
- **Low Risk**: Working legacy code exists to port from
- **Medium Complexity**: Need to adapt legacy code to new architecture  
- **High Value**: This completes the core value proposition of the tool

**Success Metrics**:
- All TODO methods implemented with actual functionality
- CLI commands work end-to-end with real file conversion
- Test coverage maintains 100% pass rate with new tests
- Performance matches or exceeds legacy scripts

## Ressourcen & Referenzen

### Key Implementation Files
- `src/calibre_books/core/converter.py` - Target implementation file
- `parallel_kfx_converter.py` - Legacy implementation to port
- `src/calibre_books/core/book.py` - ConversionResult and BookFormat definitions
- `src/calibre_books/config/manager.py` - Configuration integration
- `tests/unit/test_kfx_converter.py` - Test framework to extend

### Legacy Reference Files  
- `calibre_asin_automation.py` - Calibre integration patterns
- `book_automation_master.sh` - Orchestration patterns
- `enhanced_asin_lookup.py` - Error handling patterns

### Testing Resources
- `/Volumes/Entertainment/Bücher/Calibre-Ingest` - Test directory with books
- Existing sample books in project root (Der_*.mobi files)
- Test infrastructure in `tests/` directory

### Documentation References
- `README.md` - Current CLI documentation to update
- `CLAUDE.md` - Project configuration and commands
- `pyproject.toml` - Project dependencies and configuration

## Abschluss-Checkliste

### Core Implementation
- [ ] `convert_single()` method fully implemented and tested
- [ ] `convert_batch()` method fully implemented and tested  
- [ ] `convert_kfx_batch()` method fully implemented and tested
- [ ] `find_convertible_files()` method fully implemented and tested
- [ ] `get_supported_formats()` method dynamically implemented

### Integration
- [ ] ConfigManager integration working correctly
- [ ] CLI commands calling converter methods successfully
- [ ] Progress reporting working in CLI interface
- [ ] Error handling providing user-friendly messages
- [ ] Dry-run mode working across all conversion operations

### Quality Assurance
- [ ] All existing tests still pass (maintain 100% pass rate)
- [ ] New comprehensive unit tests for all conversion methods
- [ ] Integration tests with real files and Calibre installation
- [ ] Performance testing for batch operations
- [ ] Documentation updated to reflect actual capabilities

### User Experience
- [ ] CLI help text accurate and helpful
- [ ] Error messages clear and actionable
- [ ] Progress reporting informative during long operations
- [ ] Configuration options well-documented
- [ ] Migration path from legacy scripts clear

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-07