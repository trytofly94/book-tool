# Issue #78: Critical Fix - Book Metadata Extraction for Live Functionality

**Erstellt**: 2025-09-11
**Typ**: Critical Bug Fix / Enhancement
**Geschätzter Aufwand**: Mittel
**Verwandtes Issue**: GitHub #78 - Book metadata extraction showing 'by Unknown' instead of extracting from filename/epub

## Kontext & Ziel

**CRITICAL PRIORITY**: This issue directly blocks live functionality. All 22 test books in the pipeline show "by Unknown" instead of proper metadata extraction, preventing ASIN lookup and making batch processing completely ineffective.

**Current State**: Running `book-tool process prepare --input-dir /Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline --add-asin --check-only` shows:
- All 22 books display as "filename by Unknown"
- Example: `sanderson_elantris by Unknown` instead of `Elantris by Brandon Sanderson`
- ASIN lookup fails due to missing proper metadata

**Root Cause Identified**: The `_extract_metadata_from_filename()` method in `src/calibre_books/core/file_scanner.py` only handles " - " and " by " patterns, but test books use underscore patterns like `author_title.epub`.

## Anforderungen

**Critical Path (Must Have)**:
- [ ] Fix filename parsing for underscore patterns (`author_title.epub` → Author='Author', Title='Title')
- [ ] Test with all 22 books in `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`
- [ ] Verify ASIN lookup improvements with proper metadata extraction
- [ ] Ensure backward compatibility with existing patterns

**Enhanced Features (Should Have)**:
- [ ] Implement EPUB file metadata extraction for better quality
- [ ] Create robust fallback hierarchy: epub metadata → filename parsing → Unknown
- [ ] Handle complex patterns like `author_series#_title.epub`

**Quality Assurance (Must Have)**:
- [ ] All existing tests continue passing
- [ ] CLI commands maintain full backward compatibility
- [ ] Proper error handling and logging

## Untersuchung & Analyse

### Critical Issue Analysis
1. **Current Implementation Gap**: Line 187 in `file_scanner.py` defaults to `author="Unknown"` because underscore patterns aren't handled
2. **Test Data Perfect**: 22 Brandon Sanderson books with consistent `sanderson_title.epub` pattern
3. **Impact Assessment**: Blocks core ASIN functionality for all filename-based books

### Existing Architecture (Good Foundation)
- `_extract_metadata_from_filename()` method exists at line 167
- `_extract_metadata_from_file()` method referenced at line 189 (needs investigation)
- `_merge_metadata()` architecture in place for combining sources
- `BookMetadata` class properly structured

### Pattern Analysis from Test Books
From `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`:
- `sanderson_elantris.epub` → Should be: Title='Elantris', Author='Brandon Sanderson'
- `sanderson_mistborn1_kinder-des-nebels.epub` → Should be: Title='Mistborn 1: Kinder des Nebels', Author='Brandon Sanderson'
- `sanderson_skyward2_starsight.epub` → Should be: Title='Skyward 2: Starsight', Author='Brandon Sanderson'

**Pattern**: `lastname_title.epub` where `lastname` needs author name lookup/expansion

### Prior Art Research
- Issue #18 (ASIN lookup): ✅ Completed - ASIN infrastructure fully working
- Issue #77 (enhanced ASIN lookup): ✅ Completed - Integration ready
- Issue #87 (KFX Converter CLI): ✅ Completed - Recent successful delivery
- **No overlapping work found** - This is the logical next priority

## Implementierungsplan

### Phase 1: Immediate Fix - Underscore Pattern Support ⚡ CRITICAL
- [ ] **Analysis**: Read complete `file_scanner.py` to understand current implementation
- [ ] **Quick Fix**: Add underscore pattern parsing to `_extract_metadata_from_filename()`
  - Pattern: `author_title.ext` → split on first underscore
  - Handle: `lastname_title` → expand lastname to full author name where possible
  - Add: `author_series#_title.ext` → Author + "Series# Title"
- [ ] **Author Name Expansion**: Create simple mapping for known authors:
  - `sanderson` → `Brandon Sanderson`
  - Extensible for future authors
- [ ] **Immediate Test**: Run with pipeline books, expect dramatic improvement

### Phase 2: EPUB Metadata Integration 📚
- [ ] **Investigation**: Check if `_extract_metadata_from_file()` exists and is functional
- [ ] **Implementation**: If missing, implement EPUB metadata reading:
  - Use `zipfile` to read EPUB structure
  - Extract from `META-INF/container.xml` and content OPF
  - Read `dc:title`, `dc:creator`, `dc:identifier` elements
  - Handle encoding and XML parsing errors gracefully
- [ ] **Fallback Chain**: epub metadata → filename parsing → Unknown
- [ ] **Quality**: Prefer EPUB metadata when available and valid

### Phase 3: Comprehensive Testing with Real Books 🧪
- [ ] **Full Pipeline Test**: All 22 books should show proper author/title
- [ ] **ASIN Lookup Test**: Verify improved success rate with better metadata
- [ ] **CLI Integration Test**: Both scan and prepare commands working
- [ ] **Regression Test**: Existing books with " - " and " by " patterns still work
- [ ] **Performance Test**: No significant slowdown in file scanning

### Phase 4: Edge Cases and Polish ✨
- [ ] **Complex Patterns**: Handle edge cases like special characters, numbers
- [ ] **Multi-Author**: Handle books with multiple authors
- [ ] **Error Handling**: Graceful fallback when parsing fails completely
- [ ] **Logging**: Clear info about which method provided the metadata
- [ ] **Documentation**: Update method docstrings with new patterns

### Phase 5: Quality Assurance and Integration 🔍
- [ ] **Unit Tests**: Test new filename patterns extensively
- [ ] **Integration Tests**: Real book testing with all patterns
- [ ] **CLI Tests**: Verify all commands work with improved metadata
- [ ] **Performance**: Ensure no degradation in scan speed
- [ ] **Documentation**: Update CLI help text if needed

## Test Strategy

### Critical Path Testing
1. **Before/After Comparison**:
   - Before: `sanderson_elantris by Unknown`
   - After: `Elantris by Brandon Sanderson`

2. **Real Books Testing**:
   - All 22 books in `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`
   - Command: `book-tool process prepare --input-dir /path --add-asin --check-only`
   - Expected: Significant reduction in "by Unknown" entries

3. **ASIN Lookup Improvement**:
   - Before: 0/22 successful ASIN lookups
   - After: Expected much higher success rate with proper metadata

### Edge Case Testing
- Single word titles
- Special characters in names
- German and English mixed titles
- Numbers and series indicators
- Existing books with current patterns (regression prevention)

## Fortschrittsnotizen

### Priority Justification ✅
- **Highest Impact**: Directly blocks core ASIN functionality for all books
- **Clear Problem**: Root cause identified in `file_scanner.py` line 187
- **Perfect Test Data**: 22 books with consistent failing pattern
- **Foundation Ready**: ASIN infrastructure from Issues #18, #77 fully working
- **Immediate Benefit**: Users can immediately use ASIN lookup with filename-based books

### Implementation Readiness ✅
- **Clear Fix Location**: `src/calibre_books/core/file_scanner.py`, method `_extract_metadata_from_filename()`
- **Pattern Identified**: Add underscore splitting logic
- **Test Data Available**: Perfect real-world test cases
- **No Dependencies**: Can implement independently
- **Architecture Solid**: Good foundation to build upon

### Risk Assessment ✅
- **Low Risk**: Targeted fix in isolated method
- **Backward Compatibility**: Additive changes, existing patterns preserved
- **Testing**: Real books provide excellent validation
- **Rollback**: Easy to revert if issues arise

## Ressourcen & Referenzen

- **GitHub Issue #78**: Original issue describing the problem
- **Test Books**: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/` (22 Brandon Sanderson books)
- **Key Implementation File**: `src/calibre_books/core/file_scanner.py` (lines 167-187)
- **Related Completed Work**:
  - Issue #18: ASIN lookup infrastructure ✅
  - Issue #77: Enhanced ASIN lookup integration ✅
  - Issue #87: KFX Converter CLI integration ✅

### Command References
- **Test Scan**: `python3 -m calibre_books.cli process scan --input-dir /path`
- **Test Prepare**: `python3 -m calibre_books.cli process prepare --input-dir /path --add-asin --check-only`
- **Run Tests**: `python3 -m pytest tests/`

## Abschluss-Checkliste

### Critical Functionality ⚡
- [ ] Underscore pattern parsing implemented and working
- [ ] All 22 pipeline books show proper author/title instead of "by Unknown"
- [ ] ASIN lookup success rate significantly improved
- [ ] CLI commands work correctly with enhanced metadata

### Quality Assurance 🔍
- [ ] All existing tests continue passing (regression prevention)
- [ ] New unit tests for underscore patterns written and passing
- [ ] Integration tests with real books successful
- [ ] Performance impact minimal (under 10% slowdown acceptable)

### User Experience 🎯
- [ ] Clear improvement in CLI output (proper author/title display)
- [ ] Better ASIN lookup success rate observable
- [ ] No breaking changes to existing workflows
- [ ] Error handling graceful when parsing fails

### Documentation & Polish 📝
- [ ] Method docstrings updated with new pattern support
- [ ] Code comments explain author name expansion logic
- [ ] Any necessary CLI help text updates
- [ ] Integration with existing logging framework

---
**Status**: Aktiv - Ready for Implementation
**Zuletzt aktualisiert**: 2025-09-11
**Next Action**: Begin Phase 1 - Immediate underscore pattern fix

## Implementation Notes

**Quick Win Strategy**: Focus on Phase 1 first for immediate 80% improvement, then iterate through additional phases for completeness.

**Success Criteria**: When running the prepare command on pipeline books, see "Elantris by Brandon Sanderson" instead of "sanderson_elantris by Unknown".
