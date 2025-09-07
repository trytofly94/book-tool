# Issue #17: File Validation to Detect Corrupted eBooks Before Processing

**Erstellt**: 2025-09-07
**Typ**: Enhancement
**Geschätzter Aufwand**: Mittel
**Verwandtes Issue**: GitHub #17

## Kontext & Ziel
Implement comprehensive file validation for the book-tool CLI to detect corrupted, misnamed, or invalid eBook files before processing. This addresses critical failures discovered during Brandon Sanderson collection processing where files with wrong extensions and corrupted EPUB structures caused processing failures.

## Anforderungen
- [ ] Add `book-tool validate` command with directory scanning
- [ ] Integrate validation with existing `book-tool process` commands via `--validate-first` flag
- [ ] Implement file format detection using magic bytes and `file` command
- [ ] Add EPUB structure validation (ZIP + required components)
- [ ] Add MOBI header validation
- [ ] Detect extension/content mismatches
- [ ] Provide comprehensive validation reporting with clear status indicators
- [ ] Support batch validation with progress tracking
- [ ] Add validation caching to improve performance on repeated runs

## Untersuchung & Analyse

### Existing Codebase Architecture
- **CLI Structure**: Commands organized under `src/calibre_books/cli/` with main dispatcher in `main.py`
- **Validation Module**: Basic validation utilities exist in `src/calibre_books/utils/validation.py` (ASINs, ISBNs, file paths)
- **File Scanner**: `src/calibre_books/core/file_scanner.py` handles directory scanning and file discovery
- **Process Command**: `src/calibre_books/cli/process.py` contains existing `scan` and `prepare` commands

### Target Test Files
Located at `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/`:
1. **Invalid file**: `sanderson_sturmlicht1_weg-der-koenige.epub` (actually MS Word document)
2. **Corrupted EPUB**: `sanderson_skyward1_ruf-der-sterne.epub` (generic ZIP, not valid EPUB)
3. **Valid files**: 17 other Brandon Sanderson eBooks for comparison testing

### Related Work Analysis
- **No prior validation work**: Search through scratchpads and PRs found no existing file validation implementations
- **Test structure exists**: Unit tests in `tests/unit/test_validation.py` provide foundation for validation testing
- **CLI patterns established**: Existing commands follow consistent click-based CLI patterns with progress tracking

## Implementierungsplan

### Phase 1: Core File Validation Engine
- [ ] Extend `src/calibre_books/utils/validation.py` with file format validation functions:
  - `validate_epub_structure()` - Check ZIP structure and required EPUB components
  - `validate_mobi_header()` - Verify MOBI file headers and structure
  - `detect_file_format()` - Use magic bytes and file command for format detection
  - `check_extension_mismatch()` - Compare file extension with actual content type
- [ ] Create `src/calibre_books/core/file_validator.py` for orchestrating validation logic
- [ ] Add validation result classes and enums for structured reporting

### Phase 2: CLI Command Implementation
- [ ] Create `src/calibre_books/cli/validate.py` with comprehensive validate command:
  - `book-tool validate --input-dir ./books/` (standalone validation)
  - Support for recursive directory scanning
  - Format filtering options
  - JSON output support for programmatic use
- [ ] Add validation caching mechanism to avoid re-validating unchanged files
- [ ] Implement progress tracking using existing `ProgressManager`

### Phase 3: Integration with Existing Commands
- [ ] Extend `src/calibre_books/cli/process.py` with `--validate-first` option:
  - Add to `scan` command: `book-tool process scan --validate-first --input-dir ./books/`
  - Add to `prepare` command: `book-tool process prepare --validate-first --input-dir ./books/`
- [ ] Update `src/calibre_books/core/file_scanner.py` to optionally include validation
- [ ] Ensure validation failures prevent further processing when `--validate-first` is enabled

### Phase 4: Enhanced Validation Logic
- [ ] Implement EPUB-specific validation:
  - Check for `META-INF/container.xml` presence
  - Validate OPF file structure and metadata
  - Verify required EPUB components
- [ ] Implement MOBI-specific validation:
  - Check MOBI header magic bytes
  - Validate record structure integrity
- [ ] Add corruption detection heuristics:
  - File size consistency checks
  - ZIP integrity validation for EPUB files
  - Basic content sanity checks

### Phase 5: Comprehensive Testing
- [ ] Create unit tests in `tests/unit/test_file_validation.py`:
  - Test each validation function with known good/bad files
  - Mock file system operations for safe testing
  - Test edge cases and error conditions
- [ ] Create integration tests using the Brandon Sanderson test collection:
  - Validate against known good files (17 valid books)
  - Validate against known bad files (2 corrupted files)
  - Test CLI commands end-to-end
- [ ] Add performance benchmarks for large directory scanning

### Phase 6: CLI Integration and Documentation
- [ ] Update `src/calibre_books/cli/main.py` to register new validate command
- [ ] Add comprehensive help text and examples
- [ ] Update existing command help to mention validation options
- [ ] Ensure consistent error handling and user-friendly output
- [ ] Add validation configuration options to config system

### Phase 7: User Experience Enhancements
- [ ] Implement rich console output with color-coded validation results:
  - ✓ Valid files in green
  - ✗ Invalid files in red with detailed error descriptions
  - 📊 Summary statistics and recommendations
- [ ] Add validation report generation (HTML/JSON formats)
- [ ] Implement fix suggestions for common issues
- [ ] Add quiet mode and verbose logging options

## Fortschrittsnotizen
- **2025-09-07**: Planner completed comprehensive analysis and implementation plan
- **Target test files identified**: 19 Brandon Sanderson eBooks with 2 known corrupted files
- **Architecture integration planned**: Will extend existing validation utils and CLI structure
- **Testing strategy defined**: Unit tests + integration tests with real corrupted files

## Ressourcen & Referenzen
- GitHub Issue #17: https://github.com/trytofly94/book-tool/issues/17
- Test files location: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/`
- Existing validation module: `src/calibre_books/utils/validation.py`
- EPUB specification: https://www.w3.org/publishing/epub3/
- MOBI format documentation: Amazon Kindle file format specifications

## Abschluss-Checkliste
- [ ] File validation engine implemented with comprehensive format checks
- [ ] Standalone `validate` command functional with directory scanning
- [ ] Integration with existing `process` commands via `--validate-first` flag
- [ ] Comprehensive test suite covering unit and integration scenarios
- [ ] Rich CLI output with clear validation status and error reporting
- [ ] Documentation updated with validation command usage and examples
- [ ] Performance optimizations and caching implemented
- [ ] Validation successfully detects the 2 known corrupted files in test collection

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-07