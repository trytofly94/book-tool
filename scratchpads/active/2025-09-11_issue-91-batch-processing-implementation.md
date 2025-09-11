# Issue #91: Enhanced Features - Batch Processing Implementation

**Erstellt**: 2025-09-11
**Typ**: Feature Enhancement
**Geschätzter Aufwand**: Groß
**Verwandtes Issue**: GitHub #91 - Enhanced Features: Interactive ASIN mode, batch processing, and improved error messages

## Kontext & Ziel

Das "next issue" für das Projekt ist Issue #91, speziell die Batch Processing-Funktionalität. Dies ist perfekt abgestimmt auf die Anforderung, das System mit den Büchern im Ordner `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline` zu testen.

**Verfügbare Test-Bücher**: 18 EPUB-Dateien (0.5MB bis 15MB) hauptsächlich Brandon Sanderson Bücher - perfekte Kandidaten für Batch-Processing-Tests.

**Strategic Importance**: Diese Implementierung kombiniert alle bisherigen Arbeiten (ASIN Lookup Issue #18, KFX Converter Issue #93) zu einer umfassenden Batch-Processing-Pipeline.

## Anforderungen

- [ ] Implementiere Batch Processing Mode für mehrere Bücher gleichzeitig
- [ ] Directory-Scanning für alle unterstützten Formate (EPUB, MOBI, etc.)
- [ ] Full Pipeline Processing: ASIN Lookup + Metadata Enhancement + KFX Conversion
- [ ] Rich Progress Bars für visuelles Fortschritts-Tracking
- [ ] Individual Error Handling ohne Abbruch der gesamten Batch
- [ ] Resume Functionality für unterbrochene Batch Operations
- [ ] CLI Interface: `book-tool process batch --input-dir --output-dir`
- [ ] Test mit echten Büchern aus Pipeline-Ordner
- [ ] Performance Optimization für Parallel Processing

## Untersuchung & Analyse

### Prior Art Research

**Relevante abgeschlossene Arbeiten:**
1. **Issue #18 (ASIN Lookup)**: Vollständig implementiert und getestet - stabile Foundation
2. **Issue #93 (KFX Converter)**: Beide Legacy und CLI Architectures validiert und funktional
3. **CLI Foundation**: Pip-installierbare Package-Struktur bereits etabliert

**Existing Architecture Analysis:**
- `src/calibre_books/cli/`: CLI command structure bereits etabliert
- `src/calibre_books/core/asin_lookup.py`: ASIN Lookup Service funktional
- `src/calibre_books/core/conversion/kfx.py`: KFX Converter CLI Integration
- `parallel_kfx_converter.py`: Legacy Parallel Processing bereits implementiert

**Issue #91 Feature Breakdown:**
1. **Batch Processing Mode (Issue #69)**: HIGH priority - "significant productivity improvement"
2. **Interactive ASIN Selection (Issue #70)**: Medium priority
3. **Enhanced Error Messages (Issue #79)**: Medium priority
4. **Progress Tracking**: Medium priority
5. **Advanced ASIN Options**: Low priority

### Test Environment Analysis

**Pipeline-Ordner Content**: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`
- **18 EPUB Files**: sanderson_elantris.epub bis sanderson_tress_smaragdgruene-see.epub
- **Size Range**: 490KB (emperor-soul) bis 15.3MB (worte-des-lichts)
- **Perfect for Testing**: Consistent author, various sizes, known good content
- **Stress Test Candidates**: Large files (sturmlicht series) for performance validation

## Implementierungsplan

### Phase 1: CLI Infrastructure and Command Design

- [ ] **Batch Processing CLI Command Design**
  ```bash
  book-tool process batch --input-dir /path/to/books --output-dir /path/to/processed
  book-tool process batch --input-dir /path/to/books --formats epub,mobi --parallel 4
  book-tool process batch --resume --state-file /path/to/batch.state
  ```

- [ ] **Core CLI Implementation**
  - Erstelle `src/calibre_books/cli/batch.py` für Batch Processing Commands
  - Integriere in `src/calibre_books/cli/__init__.py` command registry
  - Implementiere argument parsing mit input-dir, output-dir, formats, parallel optionen
  - Add rich CLI interface für progress display

- [ ] **Directory Scanning Implementation**
  - Implementiere recursive directory scanning
  - File format detection und filtering (epub, mobi, pdf, etc.)
  - File validation (nicht corrupt, readable)
  - Duplicate detection und handling

### Phase 2: Batch Processing Core Engine

- [ ] **BatchProcessor Class Implementation**
  - `src/calibre_books/core/batch_processor.py`: Main batch processing engine
  - Integration mit existing ASIN Lookup Service
  - Integration mit KFX Converter (both CLI and Legacy)
  - State management für resume functionality
  - Error handling with individual failure isolation

- [ ] **Processing Pipeline Design**
  ```
  Book File → Validation → ASIN Lookup → Metadata Enhancement → Format Conversion → Output
                ↓              ↓               ↓                    ↓              ↓
             Skip Invalid   Cache Hit    Update Calibre DB    KFX/Other     Success Log
  ```

- [ ] **Parallel Processing Implementation**
  - ThreadPoolExecutor oder ProcessPoolExecutor für parallelization
  - Configurable worker count (default: CPU count)
  - Rate limiting für API calls (ASIN lookups)
  - Memory management für large files

### Phase 3: Progress Tracking and User Experience

- [ ] **Rich Progress Bars Implementation**
  - Overall batch progress (files processed / total files)
  - Individual file progress (stages: validation, ASIN, metadata, conversion)
  - Real-time statistics (success rate, errors, time remaining)
  - Rich console output mit colored status indicators

- [ ] **State Persistence and Resume**
  - JSON state file für batch operation tracking
  - Resume functionality mit `--resume` flag
  - Checkpoint system für recovery nach failures
  - State cleanup nach successful completion

- [ ] **Enhanced Error Handling and Reporting**
  - Individual file error tracking ohne batch abort
  - Detailed error reports mit suggested fixes
  - Error summary at end of batch operation
  - Option für retry failed files only

### Phase 4: Pipeline-Folder Integration Testing

- [ ] **Test Environment Setup**
  ```bash
  # Test mit Pipeline-Büchern
  book-tool process batch --input-dir "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline" --output-dir "./processed_books" --parallel 3
  ```

- [ ] **Systematic Testing Strategy**
  - **Small Batch Test**: 3 smallest files (emperor-soul, elantris, skyward1)
  - **Medium Batch Test**: 6 medium files (mistborn series)
  - **Large Batch Test**: Full 18 files mit performance monitoring
  - **Error Handling Test**: Mixed valid/invalid files

- [ ] **Performance Validation**
  - Parallel processing efficiency testing (1, 2, 4, 8 workers)
  - Memory usage monitoring mit large files
  - ASIN lookup rate limiting validation
  - KFX conversion throughput measurement

### Phase 5: Integration and Documentation

- [ ] **CLI Help and Documentation**
  - Comprehensive `--help` documentation
  - Usage examples für common scenarios
  - Error message improvements mit actionable suggestions
  - Configuration options documentation

- [ ] **Testing Suite Extension**
  - Unit tests für BatchProcessor class
  - Integration tests mit mocked file system
  - Performance regression tests
  - CLI interface tests

- [ ] **User Experience Enhancements**
  - Dry-run mode für validation ohne processing
  - Verbose logging levels (quiet, normal, verbose)
  - Configuration file support für repeated operations
  - Output format options (summary report, detailed log)

## Technische Herausforderungen

### 1. Memory Management für Large Files
**Challenge**: Pipeline enthält files bis 15MB, parallel processing könnte memory issues verursachen
**Solution**:
- Streaming file processing wo möglich
- Configurable memory limits per worker
- Progress checkpointing für recovery

### 2. API Rate Limiting Coordination
**Challenge**: Multiple parallel workers hitting ASIN lookup APIs gleichzeitig
**Solution**:
- Shared rate limiter across all workers
- Exponential backoff mit jitter
- API key rotation falls verfügbar

### 3. State Consistency für Resume
**Challenge**: Complex state management über multiple files und processing stages
**Solution**:
- Atomic state updates
- File-level granularity für resume
- Validation of state file integrity

### 4. Error Recovery and Graceful Degradation
**Challenge**: Individual file failures shouldn't abort entire batch
**Solution**:
- Exception isolation per file
- Continue processing other files
- Comprehensive error reporting and retry mechanisms

## Test-Strategie

### Unit Testing
```bash
# Core batch processor tests
python3 -m pytest tests/unit/test_batch_processor.py -v

# CLI interface tests
python3 -m pytest tests/unit/test_batch_cli.py -v
```

### Integration Testing mit Pipeline-Büchern
```bash
# Small batch test (3 files)
book-tool process batch --input-dir "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline" --output-dir "./test_output" --max-files 3 --dry-run

# Performance test mit monitoring
book-tool process batch --input-dir "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline" --output-dir "./performance_test" --parallel 4 --verbose

# Error handling test
book-tool process batch --input-dir "./mixed_valid_invalid" --output-dir "./error_test" --continue-on-error
```

### Performance Benchmarking
- Sequential vs parallel processing comparison
- Memory usage profiling
- ASIN lookup rate measurement
- Throughput analysis (books per minute)

## Erwartete Ergebnisse

### Immediate Goals
1. **Functional Batch Processing**: CLI command successfully processes multiple books
2. **Pipeline Integration**: Successful processing of 18 EPUB files aus Pipeline-Ordner
3. **Performance Optimization**: Parallel processing reduces total time significantly
4. **Error Resilience**: Individual failures don't impact batch completion

### Long-term Benefits
1. **User Productivity**: Massive improvement für users mit large book collections
2. **System Validation**: Comprehensive testing of all pipeline components
3. **Foundation für Advanced Features**: Base für interactive mode, resume functionality
4. **Performance Baseline**: Metrics für future optimizations

## Fortschrittsnotizen

[Platz für laufende Notizen über Fortschritt, Blocker und Entscheidungen]

## Ressourcen & Referenzen

- **Test Books Directory**: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline` (18 EPUB files)
- **Issue Reference**: GitHub #91 - Enhanced Features
- **Related Issues**: #69 (Batch Processing), #70 (Interactive ASIN), #79 (Error Messages)
- **Foundation Work**: Issue #18 (ASIN Lookup), Issue #93 (KFX Converter)
- **CLI Foundation**: `src/calibre_books/cli/` existing command structure
- **Core Services**: `src/calibre_books/core/asin_lookup.py`, `src/calibre_books/core/conversion/kfx.py`

## Abschluss-Checkliste

- [ ] Batch Processing CLI command implementiert und funktional
- [ ] Directory scanning und file validation working
- [ ] Full pipeline processing (ASIN + metadata + KFX) für batch operations
- [ ] Rich progress bars und user experience features
- [ ] Parallel processing mit configurable worker count
- [ ] State persistence und resume functionality
- [ ] Individual error handling ohne batch abort
- [ ] Comprehensive testing mit Pipeline-Ordner (18 EPUB files)
- [ ] Performance optimization und memory management
- [ ] Documentation und help system complete
- [ ] Integration tests und performance benchmarks passing
- [ ] Error handling validiert mit edge cases

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-11
