# Fix file format detection for DOCX and Office documents (Issue #60)

**Erstellt**: 2025-09-09
**Typ**: Bug
**Geschätzter Aufwand**: Klein
**Verwandtes Issue**: GitHub #60

## Kontext & Ziel
Die Dateiformat-Erkennung für ZIP-basierte Formate hat einen kritischen Bug, bei dem Office-Dokumente (DOCX, XLSX, PPTX) fälschlicherweise als generische ZIP-Dateien statt als ihre spezifischen Formate erkannt werden. Dies verhindert die korrekte Validierung und Verarbeitung von Office-Dokumenten im System.

## Anforderungen
- [ ] DOCX-Dateien werden korrekt als "docx" statt "zip" erkannt
- [ ] XLSX-Dateien werden als "xlsx" erkannt
- [ ] PPTX-Dateien werden als "pptx" erkannt
- [ ] EPUB-Erkennung funktioniert weiterhin korrekt
- [ ] Generische ZIP-Dateien werden weiterhin als "zip" erkannt
- [ ] Alle bestehenden Tests bestehen weiterhin
- [ ] Spezifische Test-Failures werden behoben:
  - test_detect_docx_format
  - test_mismatch_docx_as_epub
  - test_valid_azw3_header

## Untersuchung & Analyse

### Root Cause Analysis
Das Problem liegt in `src/calibre_books/utils/validation.py` in der `_detect_format_by_magic_bytes` Funktion:

1. **Zeilen 497-508**: Prüfung auf EPUB (ZIP mit mimetype)
2. **Zeilen 531+**: Prüfung auf Office-Dokumente (ZIP mit [Content_Types].xml)

**Das Problem**: Schritt 1 gibt `"zip"` für jede ZIP-Datei zurück, die keine EPUB-mimetype hat, sodass Schritt 2 niemals ausgeführt wird.

### Duplicate Logic Issue
```python
# Erste ZIP-Behandlung (Zeilen 497-508)
if header.startswith(b"PK\x03\x04"):
    # EPUB-Prüfung
    # Falls kein EPUB: return "zip"  ← HIER IST DAS PROBLEM

# Zweite ZIP-Behandlung (Zeilen 531+) - WIRD NIE ERREICHT
if header.startswith(b"PK\x03\x04"):
    # Office-Dokument-Prüfung
```

### Failing Tests Analysis
- **test_detect_docx_format**: Erwartet "docx", erhält "zip"
- **test_mismatch_docx_as_epub**: Extension-Mismatch wird nicht erkannt wegen falscher Format-Erkennung
- **test_valid_azw3_header**: AZW3-Signatur-Erkennung (verwandte Logik)

## Implementierungsplan
- [ ] Schritt 1: Code-Analyse der aktuellen ZIP-Behandlungslogik
- [ ] Schritt 2: Refactoring der ZIP-Erkennung in eine einheitliche Funktion
- [ ] Schritt 3: Implementierung der konsolidierten ZIP-Format-Erkennung:
  1. EPUB-Erkennung (mimetype = "application/epub+zip")
  2. Office-Dokument-Erkennung ([Content_Types].xml vorhanden)
  3. Generische ZIP-Erkennung (Fallback)
- [ ] Schritt 4: Fix für AZW3-Erkennung (falls nötig)
- [ ] Schritt 5: Unit-Tests ausführen und validieren
- [ ] Schritt 6: Integration-Tests mit realen Büchern aus book-pipeline
- [ ] Schritt 7: Regression-Tests für alle bestehenden Formate
- [ ] Tests und Validierung
- [ ] Dokumentations-Updates (falls nötig)

## Detaillierte Implementierung

### Vorgeschlagene Lösung
```python
# ZIP-basierte Formate (EPUB, DOCX, etc.) - KONSOLIDIERT
if header.startswith(b"PK\x03\x04"):
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            namelist = zf.namelist()

            # Prüfung auf EPUB zuerst (hat spezifische mimetype)
            if "mimetype" in namelist:
                mimetype = zf.read("mimetype").decode("utf-8").strip()
                if mimetype == "application/epub+zip":
                    return "epub"

            # Prüfung auf Office Open XML Formate
            if "[Content_Types].xml" in namelist:
                namelist_str = str(namelist)
                if "word/" in namelist_str:
                    return "docx"
                elif "xl/" in namelist_str:
                    return "xlsx"
                elif "ppt/" in namelist_str:
                    return "pptx"
                else:
                    return "office_document"

            # Falls ZIP aber weder EPUB noch Office: Plain ZIP
            return "zip"
    except zipfile.BadZipFile:
        return "corrupted_zip"
```

### Test Strategy
1. **Unit Tests**: Spezifische Test-Cases für DOCX, XLSX, PPTX
2. **Regression Tests**: Alle bestehenden EPUB/PDF/MOBI Tests
3. **Real-World Tests**: Validierung mit Büchern in `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/`
4. **Edge Cases**: Korrupte ZIP-Dateien, leere Dateien

## Fortschrittsnotizen
*[Laufende Notizen über Fortschritt, Blocker und Entscheidungen]*

## Ressourcen & Referenzen
- **GitHub Issue #60**: https://github.com/trytofly94/book-tool/issues/60
- **Related Issue #54**: Gleiche zugrunde liegende Problematik
- **Existing Scratchpad**: /scratchpads/completed/2025-09-09_issue-54-fix-file-validation-test-failures.md
- **Test Files Location**: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/`
- **Source Code**: `src/calibre_books/utils/validation.py` (Zeilen 497-540)

## Testing with Real Books
Verfügbare Test-Dateien:
- Multiple EPUB files (Brandon Sanderson collection)
- MOBI file (sanderson_mistborn-trilogy.mobi)
- Test directories for validation

**Test Plan**: Nach dem Fix alle verfügbaren Bücher verarbeiten um sicherzustellen, dass keine Regressionen in der EPUB/MOBI-Erkennung auftreten.

## Abschluss-Checkliste
- [ ] ZIP-Behandlungslogik konsolidiert
- [ ] DOCX-Format wird korrekt erkannt
- [ ] XLSX/PPTX-Formate werden erkannt
- [ ] test_detect_docx_format besteht
- [ ] test_mismatch_docx_as_epub besteht
- [ ] test_valid_azw3_header besteht
- [ ] Alle bestehenden Tests bestehen weiterhin
- [ ] Real-World-Tests mit book-pipeline Dateien erfolgreich
- [ ] Keine Regressionen in EPUB/PDF/MOBI-Erkennung
- [ ] Code-Review durchgeführt (falls zutreffend)
- [ ] Deployed/Released (falls zutreffend)

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-09
**Priorität**: Hoch (Kern-Funktionalität Bug)
**Impact**: Core file validation system
