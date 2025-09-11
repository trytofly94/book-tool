# Issue #78: Book metadata extraction showing 'by Unknown' instead of extracting from filename/epub

**Erstellt**: 2025-09-11
**Typ**: Enhancement/Bug Fix
**Geschätzter Aufwand**: Mittel
**Verwandtes Issue**: GitHub #78 - Book metadata extraction showing 'by Unknown' instead of extracting from filename/epub

## Kontext & Ziel

The current file scanning system shows books as 'filename by Unknown' instead of properly extracting title and author information from filenames or epub metadata. This prevents effective ASIN lookup and makes batch processing ineffective. We need to improve the metadata extraction to handle common filename patterns and epub file metadata.

**Test Case Available**: Perfect test books in `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/` including:
- `sanderson_elantris.epub` (should extract: Title='Elantris', Author='Brandon Sanderson')
- `sanderson_mistborn1_kinder-des-nebels.epub` (should extract: Title='Mistborn 1: Kinder des Nebels', Author='Brandon Sanderson')
- Multiple other Brandon Sanderson books with clear author_title patterns

## Anforderungen

- [ ] Fix filename parsing to extract title and author from common patterns (author_title.epub)
- [ ] Implement epub metadata extraction using epub reader
- [ ] Create fallback hierarchy: epub metadata → filename parsing → Unknown
- [ ] Test with real books in `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`
- [ ] Ensure ASIN lookup works better with extracted metadata
- [ ] Maintain backward compatibility with existing functionality
- [ ] Handle both English and German book titles

## Untersuchung & Analyse

### Current State Analysis
1. **Existing Implementation**: `src/calibre_books/core/file_scanner.py` has basic filename parsing
   - Method: `_extract_metadata_from_filename()` at line 167
   - Current patterns: " - " separator and " by " patterns
   - Missing: underscore patterns like "author_title.epub"

2. **Problem Areas**:
   - Line 174: `name_without_ext = Path(filename).stem` - correct approach
   - Lines 177-179: Only handles " - " separator, not underscores
   - No epub metadata extraction from file contents
   - Shows 'by Unknown' because author extraction fails

3. **Integration Points**:
   - File scanner creates `BookMetadata` objects
   - ASIN lookup uses title/author from metadata
   - CLI commands `process scan` and `process prepare` use this

### Prior Art Research
From completed scratchpads:
- Issue #18: ASIN lookup API failure - fully resolved, ASIN infrastructure working
- Issue #77: Enhanced ASIN lookup module integration - completed
- Multiple ASIN-related enhancements implemented and tested
- File validation system exists in `file_validator.py`

### Current Implementation Analysis
From `file_scanner.py`:
- `_extract_metadata_from_filename()` exists but limited patterns
- `_extract_metadata_from_file()` method referenced but may not be implemented
- `_merge_metadata()` method for combining filename + file metadata
- Good architecture already in place, needs enhancement

## Implementierungsplan

### Phase 1: Analysis and Requirements Gathering
- [ ] Test current behavior with pipeline books to confirm exact failure mode
- [ ] Run: `book-tool process scan --input-dir /Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline --check-asin`
- [ ] Document current output showing 'by Unknown' issue
- [ ] Analyze existing `_extract_metadata_from_filename()` implementation fully
- [ ] Check if `_extract_metadata_from_file()` exists for epub reading

### Phase 2: Filename Parsing Enhancement
- [ ] Extend `_extract_metadata_from_filename()` to handle underscore patterns
- [ ] Add pattern: `author_title.epub` → Author='Author', Title='Title'
- [ ] Add pattern: `author_title1_subtitle.epub` → Author='Author', Title='Title1: Subtitle'
- [ ] Handle capitalization and cleanup (e.g., 'sanderson' → 'Brandon Sanderson')
- [ ] Add comprehensive pattern matching for common formats:
  - `author_title.ext`
  - `author - title.ext` (existing)
  - `title by author.ext` (existing)
  - `author_series#_title.ext`

### Phase 3: EPUB Metadata Extraction
- [ ] Implement or enhance `_extract_metadata_from_file()` for epub files
- [ ] Use epub library to read metadata from epub files:
  - `dc:title` for title
  - `dc:creator` for author
  - `dc:identifier` for ISBN/ASIN
- [ ] Handle encoding and formatting issues
- [ ] Add fallback for corrupted or incomplete epub metadata

### Phase 4: Metadata Merging and Prioritization
- [ ] Enhance `_merge_metadata()` to implement proper hierarchy:
  1. EPUB file metadata (highest priority)
  2. Filename parsing
  3. Existing metadata (lowest priority)
- [ ] Ensure author names are properly formatted
- [ ] Handle multiple authors correctly
- [ ] Preserve existing ASIN if present

### Phase 5: Real-World Testing with Pipeline Books
- [ ] Test with each book in `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`
- [ ] Expected outcomes for key test cases:
  - `sanderson_elantris.epub` → Title='Elantris', Author='Brandon Sanderson'
  - `sanderson_mistborn1_kinder-des-nebels.epub` → Title='Mistborn 1: Kinder des Nebels', Author='Brandon Sanderson'
  - `sanderson_skyward1_ruf-der-sterne.epub` → Title='Skyward 1: Ruf der Sterne', Author='Brandon Sanderson'
- [ ] Verify ASIN lookup success improves with better metadata
- [ ] Test commands:
  - `book-tool process scan --input-dir /path --check-asin`
  - `book-tool process prepare --input-dir /path --add-asin --lookup`

### Phase 6: Edge Case Handling and Polish
- [ ] Handle edge cases: single words, special characters, foreign languages
- [ ] Add comprehensive error handling and logging
- [ ] Ensure graceful fallback when parsing fails
- [ ] Add unit tests for new filename patterns
- [ ] Update integration tests with real book examples

## Test Strategy

### Unit Tests
- [ ] Test filename parsing patterns with various examples
- [ ] Test epub metadata extraction with sample files
- [ ] Test metadata merging priority logic
- [ ] Mock epub reading for edge cases

### Integration Tests
- [ ] Real book testing with all 22 books in pipeline directory
- [ ] Test ASIN lookup improvement with extracted metadata
- [ ] Verify scan and prepare commands work correctly
- [ ] Test both English and German titles

### Regression Tests
- [ ] Ensure existing file scanning functionality unchanged
- [ ] Verify ASIN lookup still works for books with existing metadata
- [ ] All existing tests should continue passing
- [ ] CLI commands maintain backward compatibility

## Fortschrittsnotizen

### Research Phase ✅
- **Issue Priority Confirmed**: Issue #78 is the logical next priority after Issue #77 completion
- **Test Books Available**: Perfect test cases in `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/`
- **Existing Architecture**: Good foundation in `file_scanner.py` with methods to extend
- **Integration Ready**: ASIN lookup infrastructure from Issues #18 and #77 fully functional

### Implementation Readiness
- **Clear Requirements**: Specific filename patterns and expected outcomes defined
- **Real Test Data**: 22 Brandon Sanderson books with consistent naming patterns
- **Integration Points**: Clear understanding of where changes fit in existing code
- **Backward Compatibility**: Plan preserves existing functionality

## Ressourcen & Referenzen

- **GitHub Issue #78**: https://github.com/project/issues/78
- **Test Books Directory**: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/`
- **Key Files**:
  - `src/calibre_books/core/file_scanner.py` (main implementation)
  - `src/calibre_books/core/book.py` (BookMetadata class)
  - `src/calibre_books/cli/process.py` (CLI integration)
- **Related Issues**:
  - Issue #18 (ASIN lookup) - completed
  - Issue #77 (enhanced ASIN lookup integration) - completed
  - Issue #79 (error messages) - potential follow-up

## Abschluss-Checkliste

- [ ] Filename parsing enhanced for underscore patterns
- [ ] EPUB metadata extraction implemented
- [ ] Metadata merging priority hierarchy working
- [ ] Real book testing successful with all pipeline books
- [ ] ASIN lookup success rate improved
- [ ] Unit tests written and passing
- [ ] Integration tests with real books passing
- [ ] All existing functionality preserved
- [ ] Documentation updated
- [ ] Code-Review durchgeführt

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-11
