# Issue #49 - Parameterize Book Pipeline Path in Test Scripts

**Erstellt**: 2025-09-09
**Typ**: Enhancement
**Geschätzter Aufwand**: Klein
**Verwandtes Issue**: GitHub #49 - https://github.com/trytofly94/book-tool/issues/49

## Kontext & Ziel
Das Issue #49 zielt darauf ab, die hardcoded Book-Pipeline-Pfade in Test-Scripts zu parameterisieren, um bessere Portabilität und Testflexibilität zu erreichen. Derzeit ist der Pfad `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/` in mehreren Test-Scripts fest eingebettet, was das Testen mit alternativen Buchsammlungen verhindert und die Entwicklerumgebungsportabilität einschränkt.

## Anforderungen
- [ ] CLI-Argument-Unterstützung `--book-path /custom/path/to/books`
- [ ] Environment Variable `CALIBRE_BOOKS_TEST_PATH` Support
- [ ] Rückwärtskompatibilität mit aktuellem hardcoded Pfad als Fallback
- [ ] Configuration File Option (falls nötig)
- [ ] Dokumentations-Updates mit neuen Nutzungsbeispielen
- [ ] Test mit alternativen Buchsammlungen

## Untersuchung & Analyse

### Betroffene Test-Scripts
Durch meine Analyse habe ich folgende Test-Scripts identifiziert, die hardcoded Pfade zum book-pipeline-Verzeichnis verwenden:

**Haupt-Test-Scripts mit hardcoded Pfaden:**
1. **`test_real_availability_check.py`** - Zeile 326:
   ```python
   books_dir = Path("/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/")
   ```

2. **`test_asin_lookup_real_books.py`** - Zeile 129 & 149:
   ```python
   single_book_path = Path("/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/single-book-test/sanderson_elantris.epub")
   book_dir = Path("/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline")
   ```

3. **`test_comprehensive_review.py`** - Zeile 26:
   ```python
   test_dir = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
   ```

4. **`test_localization_comprehensive.py`** - Zeile 35, 168, 209:
   ```python
   self.test_directory = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
   pipeline_base = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
   pipeline_base = "/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"
   ```

**Weitere betroffene Scripts:**
- `test_issue_23_language_validation.py`
- Verschiedene andere Test-Scripts mit ähnlichen hardcoded Pfaden

### Verwandte Arbeiten
Nach Recherche in den Scratchpads wurden viele Issues zu Testing und ASIN-Lookup behandelt (#18, #19, #23, etc.), aber keines hat sich spezifisch mit der Parameterisierung der Pfade beschäftigt. Dies ist das erste Issue, das diese Quality-of-Life Verbesserung angeht.

### Anti-Overengineering Prinzipien
- **Einfache Lösung bevorzugen**: CLI-Argumente mit Environment Variable Fallback
- **Bestehende Patterns wiederverwenden**: Ähnliche Argument-Parsing-Patterns in bestehenden Scripts nutzen
- **Modularität planen**: Zentrale Pfad-Resolution-Funktion für alle Test-Scripts

## Implementierungsplan

### Phase 1: Zentrale Pfad-Resolution-Funktion erstellen
- [ ] **Schritt 1.1**: Neue Utility-Funktion `get_test_book_path()` erstellen
  - Implementierung in `src/calibre_books/utils/test_helpers.py` (oder neues Modul)
  - Unterstützung für CLI-Argumente, Environment Variables und Fallback
  - Validierung des Pfades auf Existenz und Berechtigung

- [ ] **Schritt 1.2**: Argument-Parser-Helper erstellen
  - Wiederverwendbare `add_book_path_argument()` Funktion für argparse
  - Standard-Help-Text und Validierung
  - Konsistente CLI-Interface-Patterns

### Phase 2: Test-Scripts refactoren (Priorität: Häufig genutzte Scripts)
- [ ] **Schritt 2.1**: `test_real_availability_check.py` refactoren
  - argparse integration
  - Environment Variable Support
  - Fallback-Verhalten implementieren

- [ ] **Schritt 2.2**: `test_asin_lookup_real_books.py` refactoren
  - CLI-Argumente für book-path und single-book-path
  - Dynamische Pfad-Resolution

- [ ] **Schritt 2.3**: `test_comprehensive_review.py` refactoren
  - Parametrisierung des test_dir
  - CLI-Interface hinzufügen

- [ ] **Schritt 2.4**: `test_localization_comprehensive.py` refactoren
  - self.test_directory parameterisierbar machen
  - Alle hardcoded pipeline_base Referenzen ersetzen

### Phase 3: Erweiterte Test-Scripts refactoren
- [ ] **Schritt 3.1**: Restliche Test-Scripts identifizieren und refactoren
- [ ] **Schritt 3.2**: Batch-Refactoring für kleinere Test-Scripts

### Phase 4: Configuration File Support (Optional)
- [ ] **Schritt 4.1**: Evaluieren ob Configuration File nötig ist
- [ ] **Schritt 4.2**: Falls nötig: JSON/YAML Config Support implementieren

### Phase 5: Tests und Validierung
- [ ] **Schritt 5.1**: Unit-Tests für die neue Pfad-Resolution-Funktion schreiben
- [ ] **Schritt 5.2**: Integration-Tests mit verschiedenen Pfad-Konfigurationen
- [ ] **Schritt 5.3**: Rückwärtskompatibilität testen (ohne Argumente)
- [ ] **Schritt 5.4**: Test mit User-spezifischem Pfad: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`

### Phase 6: Dokumentations-Updates
- [ ] **Schritt 6.1**: README.md updaten mit neuen CLI-Optionen
- [ ] **Schritt 6.2**: Docstrings in allen Test-Scripts updaten
- [ ] **Schritt 6.3**: Help-Text für alle CLI-Argumente

## Fortschrittsnotizen
- **2025-09-09**: Issue analysiert, 10+ Test-Scripts mit hardcoded Pfaden identifiziert
- **2025-09-09**: Implementierungsplan erstellt mit 6 Phasen
- Bereit für Creator-Agent Übergabe

## Ressourcen & Referenzen
- **GitHub Issue #49**: https://github.com/trytofly94/book-tool/issues/49
- **Betroffene Test-Scripts**: Alle test_*.py Files mit book-pipeline Pfaden
- **User's Test-Pfad**: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`
- **Python argparse Dokumentation**: https://docs.python.org/3/library/argparse.html

## Technische Details

### Vorgeschlagene CLI-Interface:
```bash
# Mit CLI-Argument
python test_real_availability_check.py --book-path /custom/path/to/books

# Mit Environment Variable
export CALIBRE_BOOKS_TEST_PATH=/custom/path/to/books
python test_real_availability_check.py

# Fallback zum Standard-Pfad (Rückwärtskompatibilität)
python test_real_availability_check.py
```

### Zentrale Utility-Funktion Design:
```python
def get_test_book_path(cli_args=None, env_var="CALIBRE_BOOKS_TEST_PATH",
                       default_path="/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline"):
    """
    Resolve test book directory path from CLI args, environment, or default.

    Priority: CLI args > Environment Variable > Default Path
    """
    # Implementation details...
```

### Environment Variable:
- **Name**: `CALIBRE_BOOKS_TEST_PATH`
- **Zweck**: Ermöglicht globale Konfiguration ohne CLI-Argumente
- **Fallback**: Standard hardcoded Pfad bleibt bestehen

## Abschluss-Checkliste
- [ ] Zentrale Pfad-Resolution implementiert
- [ ] Alle identifizierten Test-Scripts refactored
- [ ] CLI-Argumente und Environment Variable Support funktional
- [ ] Unit-Tests geschrieben und bestanden
- [ ] Integration-Tests mit verschiedenen Pfaden erfolgreich
- [ ] Rückwärtskompatibilität bestätigt
- [ ] Dokumentation aktualisiert
- [ ] Code-Review durchgeführt (falls zutreffend)

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-09
