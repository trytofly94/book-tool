# Issue #17 - File Validation to Detect Corrupted eBooks Before Processing

**Erstellt**: 2025-09-08
**Typ**: Enhancement
**Geschätzter Aufwand**: Mittel
**Verwandtes Issue**: GitHub #17

## Kontext & Ziel
Implementierung einer File-Validation-Funktionalität, um korrupte oder falsch benannte eBook-Dateien vor der Verarbeitung zu erkennen. Dies verhindert Zeitverschwendung bei der Batch-Verarbeitung und bietet klares Feedback über Dateistatus.

**Real-world Problem**: Im Test-Verzeichnis `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline` befinden sich nachweislich korrupte Dateien:
- `sanderson_sturmlicht1_weg-der-koenige.epub` - tatsächlich MS Word Document  
- `sanderson_skyward1_ruf-der-sterne.epub` - korrupte EPUB-Struktur (nur ZIP ohne EPUB-Content)

## Anforderungen
- [ ] Standalone CLI-Kommando `book-tool validate --input-dir ./books/`
- [ ] Integration in bestehende Processing-Workflows mit `--validate-first` Option
- [ ] File-Format-Verification über magic bytes/file command
- [ ] EPUB-Struktur-Validation (mimetype, META-INF, OEBPS Verzeichnisse)
- [ ] MOBI-Header-Validation für .mobi Dateien
- [ ] Extension/Content-Mismatch-Erkennung
- [ ] Detailliertes Reporting mit Status pro Datei
- [ ] Batch-Processing-Unterstützung für große Verzeichnisse

## Untersuchung & Analyse

### Prior Art Recherche
- **Scratchpad-Suche**: Keine existierenden File-Validation-Implementierungen gefunden
- **PR-Suche**: Keine verwandten Pull Requests zu File-Validation
- **Issue-Status**: Issue #17 offen, keine bestehende Arbeit

### Test-Daten-Analyse (Perfekte Validierung verfügbar)
```bash
# Korrupte Dateien identifiziert:
file sanderson_sturmlicht1_weg-der-koenige.epub
# Output: Composite Document File V2 Document (MS Word)

file sanderson_skyward1_ruf-der-sterne.epub  
# Output: Zip archive data (korrupte EPUB)

file sanderson_elantris.epub
# Output: EPUB document (valide Referenz)
```

### Aktuelle CLI-Architektur
- **Package-Struktur**: `src/calibre_books/` mit `cli/`, `core/`, `utils/`, `config/`
- **Integration-Punkt**: Neue Validation-Module in `core/validation/`
- **CLI-Extension**: Neuer Befehl in `cli/commands/validate.py`

## Implementierungsplan

### Phase 1: Core Validation Engine
- [ ] Erstelle `src/calibre_books/core/validation/` Modul
- [ ] Implementiere `FileValidator` Klasse mit magic bytes Erkennung
- [ ] Implementiere `EpubValidator` für EPUB-spezifische Checks
- [ ] Implementiere `MobiValidator` für MOBI-spezifische Checks  
- [ ] Erstelle `ValidationResult` Data-Klassen für strukturierte Ergebnisse

### Phase 2: CLI-Integration
- [ ] Erstelle `src/calibre_books/cli/commands/validate.py`
- [ ] Implementiere `book-tool validate` Kommando mit argparse
- [ ] Add `--input-dir`, `--recursive`, `--output-format` (text/json) Optionen
- [ ] Implementiere detailliertes Reporting mit Zusammenfassung

### Phase 3: Workflow-Integration  
- [ ] Erweitere bestehende Processing-Befehle um `--validate-first` Option
- [ ] Integriere Validation in Batch-Processing-Workflows
- [ ] Implementiere Fail-Fast vs. Continue-on-Error Modi

### Phase 4: Testing & Validation
- [ ] Unit-Tests für alle Validation-Klassen mit Mock-Files
- [ ] Integration-Tests mit echten Test-Dateien aus book-pipeline
- [ ] Performance-Tests für große Verzeichnisse
- [ ] Edge-Case-Tests (leere Dateien, Permissions, etc.)

### Phase 5: Dokumentation & Finalisierung
- [ ] CLI-Help-Dokumentation
- [ ] Usage-Examples in README
- [ ] Error-Handling und User-Friendly-Messages
- [ ] Integration in bestehende Workflows dokumentieren

## Fortschrittsnotizen
- **2025-09-08**: Projekt-Analyse abgeschlossen, Issue #17 als höchste Priorität identifiziert
- **Grund für Priorität**: Reale User-Probleme, perfekte Test-Daten verfügbar, hohe Impact auf UX
- **Test-Daten**: Optimale Validierung mit bekannt korrupten Dateien in book-pipeline Verzeichnis

## Ressourcen & Referenzen
- **GitHub Issue**: https://github.com/user/book-tool/issues/17
- **Test-Verzeichnis**: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`
- **Korrupte Test-Dateien**: 
  - `sanderson_sturmlicht1_weg-der-koenige.epub` (MS Word)
  - `sanderson_skyward1_ruf-der-sterne.epub` (korrupte EPUB)
- **Python file/magic Bibliotheken**: `python-magic`, `filetype`
- **EPUB-Standard**: EPUB 3.0 Spezifikation für Struktur-Validation

## Technische Implementierungs-Details

### File-Detection-Strategien
1. **Magic Bytes**: `python-magic` oder `filetype` für binäre Erkennung
2. **Extension-Matching**: Vergleich erwarteter vs. tatsächlicher Format
3. **Struktur-Validation**: ZIP-Entpackung und EPUB-Komponenten-Check
4. **Metadata-Extraction**: Calibre-Integration für erweiterte Validation

### CLI-Command-Design
```bash
# Standalone validation
book-tool validate --input-dir ./books/ --output-format json

# Integration in processing  
book-tool process --validate-first --input-dir ./books/ --output-dir ./processed/

# Detailed reporting
book-tool validate --input-dir ./books/ --recursive --verbose
```

### Expected Output Format
```
✓ sanderson_elantris.epub - Valid EPUB (1.05MB)
✗ sanderson_sturmlicht1_weg-der-koenige.epub - Invalid: MS Word document (expected EPUB)
✗ sanderson_skyward1_ruf-der-sterne.epub - Corrupted: Invalid EPUB structure
⚠ sanderson_mistborn1.mobi - Warning: Large file size (4.4MB)

📊 Validation Summary:
- Total files: 20
- Valid: 17 (85%)  
- Invalid: 2 (10%)
- Warnings: 1 (5%)
- Time: 2.3s
```

## Abschluss-Checkliste
- [ ] Kernfunktionalität implementiert (FileValidator, EpubValidator, MobiValidator)
- [ ] CLI-Kommando `book-tool validate` funktional
- [ ] Integration in bestehende Workflows (`--validate-first`)
- [ ] Comprehensive Tests mit realen korrupten Test-Dateien
- [ ] Performance-Optimierung für Batch-Processing
- [ ] Dokumentation aktualisiert (CLI help, README, examples)
- [ ] Code-Review durchgeführt
- [ ] User-Acceptance-Tests mit book-pipeline Testdaten

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-08
**Nächster Schritt**: Phase 1 - Core Validation Engine Implementation