# Projekt-Konfiguration für Calibre Book Automation CLI

## 1. Technologie-Stack
- **Sprache**: Python 3.9+
- **Framework/Runtime**: Python Standard Library, CLI-basiert
- **Paketmanager**: pip
- **Haupt-Abhängigkeiten**:
  - requests (HTTP-Anfragen für ASIN-Lookup)
  - beautifulsoup4 (HTML-Parsing für Web-Scraping)
  - selenium (Browser-Automatisierung für erweiterte Suchen)
  - webdriver-manager (Chrome WebDriver Management)
  - subprocess (CLI-Integration mit Calibre Tools)

## 2. Wichtige Befehle
- **Abhängigkeiten installieren**: `pip install requests beautifulsoup4 selenium webdriver-manager`
- **Master Automation starten**: `./book_automation_master.sh`
- **ASIN Automation ausführen**: `python3 calibre_asin_automation.py`
- **KFX Konvertierung starten**: `python3 parallel_kfx_converter.py`
- **Book Download**: `python3 auto_download_books.py`
- **Tests ausführen**: `python3 -m pytest tests/` (nach Einrichtung)
- **Linter ausführen**: `python3 -m flake8 .` (nach Installation)

## 3. Architektur-Übersicht
- **Kern-Logik Verzeichnis**: Haupt-Python-Scripts im Root-Verzeichnis
- **CLI-Entry-Points**:
  - `book_automation_master.sh` (Master-Orchestrator)
  - Individual Python scripts für spezifische Aufgaben
- **Konfigurationsdateien**:
  - Hardcoded Pfade in Scripts (werden zu CLI-Optionen)
  - Cache-Dateien in `/tmp/` für ASIN-Lookups
- **Externe Abhängigkeiten**:
  - Calibre CLI Tools (`calibredb`, `ebook-convert`, `ebook-meta`)
  - `librarian` CLI für Book Downloads
  - Chrome Browser + WebDriver für Selenium

## 4. System-Voraussetzungen
- **macOS/Linux** (Pfade sind Unix-basiert)
- **Calibre** installiert mit CLI-Tools im PATH
- **Chrome Browser** für Selenium-basierte ASIN-Lookups
- **librarian CLI** für automatisierte Book Downloads
- **Python 3.9+** mit pip

## 5. Aktuelle Projekt-Struktur
- `calibre_asin_automation.py`: ASIN-Management für Calibre-Metadaten
- `enhanced_asin_lookup.py`: Multi-Source ASIN-Lookup Service
- `parallel_kfx_converter.py`: Parallel KFX-Konvertierung für Goodreads
- `auto_download_books.py`: Automatisierter Book Download
- `book_automation_master.sh`: Master-Orchestrator Script
- `calibre_*.py`: Verschiedene Calibre-Integration-Scripts

## 6. Transformations-Ziele für CLI-Tool
- **Package Structure**: Umwandlung in installierbare Python-Package mit `setup.py`/`pyproject.toml`
- **CLI Interface**: Ersetzung der Shell-Scripts durch `argparse`-basierte CLI
- **Configuration**: Externalisierung der hardcoded Pfade in Konfigurationsdateien
- **Testing**: Einrichtung einer Test-Suite mit `pytest`
- **Documentation**: Vollständige README und API-Dokumentation

## 7. Hinweise für die Agenten
- **Für den Planner-Agent**: Diese Scripts sind funktional aber nicht als Package strukturiert. Transformation zu CLI-Tool erfordert Refactoring der Architektur.
- **Für den Creator-Agent**:
  - Bitte halte dich an PEP8 Python Code-Stil
  - Verwende `argparse` für CLI-Interfaces
  - Implementiere proper logging statt print-Statements
  - Externalisiere Konfiguration aus hardcoded Werten
- **Für den Tester-Agent**:
  - Erstelle Unit-Tests mit `pytest`
  - Mock externe Dependencies (Calibre, librarian, Selenium)
  - Teste CLI-Interfaces mit verschiedenen Argumenten
  - Simuliere Dateisystem-Operationen für sichere Tests
- **Für den Deployer-Agent**:
  - Erstelle `setup.py` oder `pyproject.toml` für pip-Installation
  - Dokumentiere Installation und Setup in README
  - Stelle sicher, dass alle externen Dependencies dokumentiert sind

## 8. Kritische Abhängigkeiten
- **Calibre CLI Tools**: Müssen im System-PATH verfügbar sein
- **librarian**: Externe CLI für Book Downloads (Installation separat erforderlich)
- **Chrome + WebDriver**: Für Selenium-basierte Web-Scraping Funktionalität
