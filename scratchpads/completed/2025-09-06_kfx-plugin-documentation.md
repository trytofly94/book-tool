# Add Documentation: KFX requires Calibre KFX Output Plugin Installation

**Erstellt**: 2025-09-06
**Typ**: Documentation
**Geschätzter Aufwand**: Klein-Mittel
**Verwandtes Issue**: GitHub #5 - Add documentation: KFX requires Calibre KFX Output plugin installation

## Kontext & Ziel

Dokumentiere die kritische Abhängigkeit des KFX Output Plugins für Calibre, um Benutzer über die notwendigen Voraussetzungen für KFX-Konvertierungen zu informieren. Das Ziel ist es, eine benutzerfreundliche Dokumentation zu erstellen, die Benutzern hilft, das KFX Output Plugin korrekt zu installieren und die Verfügbarkeit zu überprüfen.

### Problem Definition
- Benutzer erhalten kryptische Fehlermeldungen bei KFX-Konvertierungen ohne zu wissen, dass das KFX Output Plugin fehlt
- KFX ist das kritische Format für Kindle Goodreads Integration
- Fehlende Dokumentation führt zu Zeitverschwendung bei der Fehlersuche
- Tool sollte Plugin-Verfügbarkeit prüfen und Benutzer warnen

## Anforderungen

### Dokumentations-Anforderungen
- [ ] README.md um KFX Plugin Voraussetzungen erweitern
- [ ] Schritt-für-Schritt Installationsanleitung für KFX Output Plugin
- [ ] Plugin-Verfügbarkeits-Prüfung dokumentieren (`calibre-customize -l | grep KFX`)
- [ ] Fehlerbehebungs-Sektion für häufige Plugin-Probleme
- [ ] Integration in CLI-Hilfe und Fehlerbehandlung

### Funktionale Anforderungen
- [ ] CLI-Kommando zur Plugin-Verfügbarkeits-Prüfung erweitern
- [ ] Bessere Fehlermeldungen bei fehlendem KFX Plugin
- [ ] `book-tool config init` sollte Plugin-Verfügbarkeit prüfen und warnen
- [ ] System Requirements Check sollte KFX Plugin Status anzeigen

### Benutzerfreundlichkeits-Anforderungen
- [ ] Klare Installationsschritte mit Screenshots (optional)
- [ ] Verlinkung zu offiziellen Plugin-Quellen
- [ ] Warnung vor inoffiziellen Plugin-Versionen
- [ ] Troubleshooting Guide für häufige Probleme

## Untersuchung & Analyse

### Prior Art Analysis

**Verwandte Scratchpads gefunden:**
1. **`2025-09-05_fix-kfx-config-manager-interface.md`** (aktiv): Behebt KFX ConfigManager Bug - relevant für Integration von Plugin-Checks
2. **`2025-09-05_calibre-cli-tool-transformation.md`** (abgeschlossen): Architektur-Grundlage des CLI Tools
3. **`2025-09-06_asin-lookup-implementation.md`** (abgeschlossen): ASIN Lookup Implementierung 
4. **`2025-09-06_issue4-final-validation-testing.md`** (abgeschlossen): ConfigManager Validierung

**Keine verwandten Pull Requests gefunden** - das ist die erste Dokumentationsaufgabe für KFX Plugin Requirements.

### Aktuelle Code-Analyse

**KFX-bezogene Dateien identifiziert (31 Dateien):**
- `/src/calibre_books/core/converter.py`: FormatConverter mit KFX-Unterstützung
- `/src/calibre_books/core/downloader.py`: KFXConverter Implementation 
- `/src/calibre_books/cli/convert.py`: CLI KFX Convert Commands
- `/tests/integration/test_kfx_conversion_cli.py`: KFX Integration Tests
- `/tests/unit/test_kfx_converter.py`: KFX Unit Tests

**Aktuelle Plugin-Validierung in `converter.py` (Zeilen 53-59):**
```python
def validate_kfx_plugin(self) -> bool:
    """Validate that KFX Input plugin is available in Calibre."""
    self.logger.info("Validating KFX plugin availability")
    
    # TODO: Implement actual plugin validation
    # This is a placeholder implementation
    return True
```

**CLI System Requirements Check in `convert.py` (Zeilen 83-100):**
```python
if check_requirements:
    console.print("[cyan]Checking KFX conversion requirements...[/cyan]")
    requirements = converter.check_system_requirements()
    
    table = Table(title="System Requirements")
    # ...
    status_map = {
        'calibre': 'Calibre GUI application',
        'ebook-convert': 'Calibre ebook-convert tool',
        'kfx_plugin': 'KFX Output Plugin for Calibre',  # ← Erwähnt, aber nicht implementiert
        'kindle_previewer': 'Kindle Previewer 3'
    }
```

**Aktuelle README.md Struktur:**
- Prerequisites Section (Zeilen 14-25): Listet Calibre auf, aber nicht das KFX Plugin
- Installation Section (Zeilen 26-73): Vollständig, aber ohne KFX Plugin Details
- Troubleshooting Section (Zeilen 141-152): Grundlegend, aber ohne KFX Plugin Probleme

### Issue #5 Details Analysis

**Kritische Erkenntnisse aus dem Issue:**
- Plugin-Prüfung: `calibre-customize -l | grep KFX`
- Erwartete Ausgabe: `KFX Output (2, 17, 1) - Convert ebooks to KFX format`
- Plugin-Autor: jhowell (wichtig für Authentizität)
- Installation über Calibre GUI: Preferences → Plugins → Get new plugins
- Neustart von Calibre nach Installation erforderlich

**Beziehung zu anderen Issues:**
- Issue #1: KFX conversion ConfigManager bug (BEHOBEN)
- Issue #3: ASIN lookup not implemented (BEHOBEN) 
- Issue #4: ConfigManager.get() method error (BEHOBEN)
- Issue #5 ist kritisch für die Benutzerfreundlichkeit des KFX Features

### Test-Verzeichnis Analysis
**Möglicher Test-Ordner:** `/Volumes/Entertainment/Bücher/Calibre-Ingest`
- Benutzer sollen dort Testen können
- Dokumentation sollte Beispiel-Pfade für diesen Ordner enthalten
- Wichtig für lokale Validierung der KFX-Funktionalität

## Implementierungsplan

### Phase 1: README.md Dokumentation erweitern
- [ ] **Schritt 1.1**: Prerequisites Section um KFX Plugin erweitern
  - Detaillierte KFX Output Plugin Installation hinzufügen
  - Plugin-Verfügbarkeits-Prüfung mit `calibre-customize -l | grep KFX` dokumentieren
  - Offiziellen Plugin-Autor (jhowell) erwähnen für Sicherheit

- [ ] **Schritt 1.2**: KFX Prerequisites Untersektion erstellen
  ```markdown
  ### KFX Conversion Prerequisites
  
  For KFX conversion functionality, you need:
  1. Calibre with KFX Output Plugin installed
  2. Plugin verification steps
  3. Troubleshooting common issues
  ```

- [ ] **Schritt 1.3**: Installation Guide erweitern
  - Schritt-für-Schritt KFX Plugin Installation
  - Screenshots oder ASCII-Art für GUI-Navigation (optional)
  - Plugin-Restart-Anforderung dokumentieren

- [ ] **Schritt 1.4**: Troubleshooting Section erweitern
  - Häufige KFX Plugin Probleme
  - Plugin nicht gefunden Fehlermeldungen
  - Inkompatible Plugin-Versionen
  - Calibre Neustart-Probleme

### Phase 2: CLI Integration und System Requirements Check
- [ ] **Schritt 2.1**: `validate_kfx_plugin()` Implementierung vervollständigen
  - Tatsächliche Plugin-Prüfung mit `calibre-customize -l` subprocess
  - KFX Output Plugin Erkennung mit Regex/String-Matching
  - Version-Erkennung für bessere Diagnose
  - Logging für Debug-Zwecke

- [ ] **Schritt 2.2**: System Requirements Check erweitern
  - `check_system_requirements()` in KFXConverter implementieren
  - Plugin-Status in Requirements Table anzeigen
  - Detaillierte Fehlermeldungen bei fehlendem Plugin

- [ ] **Schritt 2.3**: `book-tool config init` KFX Plugin Warnung
  - Plugin-Check während Konfiguration-Initialisierung
  - Warnung ausgeben wenn Plugin fehlt
  - Link zur Installationsanleitung in der Warnung

### Phase 3: Erweiterte Fehlerbehandlung und Benutzerführung
- [ ] **Schritt 3.1**: CLI Error Messages verbessern
  - Spezifische Fehlermeldung bei fehlendem KFX Plugin
  - Hinweis auf Installation-Guide in Fehlermeldung
  - Plugin-Check vor KFX Conversion Attempts

- [ ] **Schritt 3.2**: Help-Text erweitern
  - `book-tool convert kfx --help` um Plugin-Anforderungen erweitern
  - Beispiele für Plugin-Verfügbarkeits-Prüfung hinzufügen
  - Link zu Prerequisites Documentation

- [ ] **Schritt 3.3**: Interactive Plugin Installation Guide (optional)
  - `book-tool plugins install-kfx` Kommando (optional)
  - Interaktive Anleitung für Plugin-Installation
  - Verfügbarkeits-Prüfung nach Installation

### Phase 4: Testing und Validierung
- [ ] **Schritt 4.1**: Plugin-Detection Tests schreiben
  - Unit-Tests für `validate_kfx_plugin()` Funktionalität
  - Mock-Tests für verschiedene Plugin-Status-Szenarien
  - Integration-Tests für System Requirements Check

- [ ] **Schritt 4.2**: Documentation Tests
  - Validierung dass alle Links funktionieren
  - Überprüfung der Installation-Schritte auf verschiedenen Systemen
  - User Experience Testing mit Test-Verzeichnis `/Volumes/Entertainment/Bücher/Calibre-Ingest`

- [ ] **Schritt 4.3**: End-to-End Validation
  - Kompletter Workflow: Installation → Plugin Check → KFX Conversion
  - Fehlerszenario-Tests: Fehlendes Plugin → Hilfreiche Fehlermeldung
  - Performance-Check: Plugin-Detection sollte schnell sein (< 1s)

## Detaillierte Code-Änderungen

### File: `README.md` (Hauptänderungen)

**Neue Prerequisites Section (nach Zeile 25):**
```markdown
### KFX Conversion Prerequisites

KFX conversion requires the **KFX Output Plugin** for Calibre:

#### Install KFX Output Plugin

1. Open Calibre
2. Go to **Preferences** → **Plugins**
3. Click **Get new plugins**
4. Search for **"KFX Output"**
5. Install the plugin by **jhowell** (ensure authenticity)
6. **Restart Calibre** (important!)

#### Verify Plugin Installation

Check that the plugin is properly installed:

```sh
calibre-customize -l | grep KFX
```

Expected output:
```
KFX Output (2, 17, 1) - Convert ebooks to KFX format
Set KFX metadata (2, 17, 1) - Set metadata in KFX files
```

#### Plugin Troubleshooting

- **Plugin not found**: Ensure you restart Calibre after installation
- **Wrong version**: Use only the official plugin by jhowell
- **Conversion fails**: Run `book-tool convert kfx --check-requirements`
```

**Erweiterte Troubleshooting Section (nach Zeile 150):**
```markdown
### KFX Conversion Issues

1. **KFX Plugin not installed**: Follow the KFX Prerequisites guide above
2. **Plugin not detected**: Restart Calibre and verify with `calibre-customize -l | grep KFX`
3. **Conversion errors**: Check system requirements with `book-tool convert kfx --check-requirements`
4. **Wrong plugin version**: Uninstall and reinstall the official KFX Output plugin by jhowell
```

### File: `src/calibre_books/core/converter.py`

**Vervollständigung der `validate_kfx_plugin()` Methode (Zeilen 53-59):**
```python
def validate_kfx_plugin(self) -> bool:
    """Validate that KFX Output plugin is available in Calibre."""
    import subprocess
    import re
    
    self.logger.info("Validating KFX plugin availability")
    
    try:
        # Run calibre-customize to list plugins
        result = subprocess.run(
            ['calibre-customize', '-l'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            self.logger.error(f"Failed to list Calibre plugins: {result.stderr}")
            return False
        
        # Check for KFX Output plugin
        kfx_pattern = r'KFX Output.*Convert ebooks to KFX format'
        if re.search(kfx_pattern, result.stdout, re.IGNORECASE):
            self.logger.info("KFX Output plugin found and available")
            return True
        else:
            self.logger.warning("KFX Output plugin not found. Please install it via Calibre Preferences → Plugins")
            return False
            
    except subprocess.TimeoutExpired:
        self.logger.error("Timeout while checking Calibre plugins")
        return False
    except FileNotFoundError:
        self.logger.error("calibre-customize command not found. Please install Calibre CLI tools")
        return False
    except Exception as e:
        self.logger.error(f"Unexpected error checking KFX plugin: {e}")
        return False
```

### File: `src/calibre_books/core/downloader.py`

**Erweiterte `check_system_requirements()` Methode:**
```python
def check_system_requirements(self) -> Dict[str, bool]:
    """Check if all system requirements for KFX conversion are met."""
    requirements = {}
    
    # Check Calibre CLI tools
    requirements['calibre'] = self._check_calibre_available()
    requirements['ebook-convert'] = self._check_ebook_convert_available()
    
    # Check KFX plugin availability
    requirements['kfx_plugin'] = self.validate_kfx_plugin()
    
    # Optional: Check Kindle Previewer
    requirements['kindle_previewer'] = self._check_kindle_previewer_available()
    
    return requirements

def validate_kfx_plugin(self) -> bool:
    """Validate KFX plugin - delegate to FormatConverter if available."""
    try:
        from ..core.converter import FormatConverter
        # Use the same validation logic as FormatConverter
        temp_converter = FormatConverter(self.config_manager)
        return temp_converter.validate_kfx_plugin()
    except Exception as e:
        self.logger.error(f"Failed to validate KFX plugin: {e}")
        return False
```

### File: `src/calibre_books/cli/convert.py`

**Erweiterte Fehlerbehandlung für KFX Conversion (nach Zeile 80):**
```python
try:
    converter = KFXConverter(config)
    
    # Check KFX plugin before attempting conversion
    if not converter.validate_kfx_plugin():
        console.print("[red]Error: KFX Output plugin not found![/red]")
        console.print("Please install the KFX Output plugin:")
        console.print("1. Open Calibre → Preferences → Plugins")
        console.print("2. Get new plugins → Search 'KFX Output'")
        console.print("3. Install plugin by jhowell and restart Calibre")
        console.print("\nFor details: https://github.com/trytofly94/book-tool#kfx-conversion-prerequisites")
        raise click.ClickException("KFX Output plugin required for KFX conversion")
```

### File: `src/calibre_books/cli/config.py`

**Plugin-Warnung in Config Init (erweitern):**
```python
@config.command()
@click.option("--interactive", is_flag=True, help="Interactive configuration setup")
def init(interactive: bool):
    """Initialize configuration file with default values."""
    
    # ... existing config initialization ...
    
    # Check KFX plugin availability and warn if missing
    try:
        from ..core.converter import FormatConverter
        from ..config.manager import ConfigManager
        
        temp_config = ConfigManager()
        temp_converter = FormatConverter(temp_config)
        
        if not temp_converter.validate_kfx_plugin():
            console.print("\n[yellow]Warning: KFX Output plugin not detected[/yellow]")
            console.print("KFX conversion will not work without this plugin.")
            console.print("Install it via: Calibre → Preferences → Plugins → Get new plugins → 'KFX Output'")
            console.print("See: https://github.com/trytofly94/book-tool#kfx-conversion-prerequisites")
    except Exception:
        pass  # Don't fail config init if plugin check fails
```

## Testing Strategy

### Unit Tests (`tests/unit/test_kfx_plugin_validation.py` - neu)
```python
def test_validate_kfx_plugin_success():
    """Test successful KFX plugin detection."""
    
def test_validate_kfx_plugin_not_found():
    """Test behavior when KFX plugin is not installed."""
    
def test_validate_kfx_plugin_calibre_not_available():
    """Test behavior when Calibre CLI tools are not available."""

def test_system_requirements_check_includes_kfx_plugin():
    """Test that system requirements check includes KFX plugin status."""
```

### Integration Tests (`tests/integration/test_kfx_documentation_integration.py` - neu)
```python
def test_kfx_conversion_fails_gracefully_without_plugin():
    """Test that KFX conversion provides helpful error message when plugin missing."""

def test_config_init_warns_about_missing_kfx_plugin():
    """Test that config initialization warns about missing KFX plugin."""

def test_help_text_includes_kfx_requirements():
    """Test that help text mentions KFX plugin requirements."""
```

## Fortschrittsnotizen

**2025-09-06**: Detaillierte Analyse von GitHub Issue #5 abgeschlossen. Plan erstellt für umfassende KFX Plugin Dokumentation und Integration.

**Schlüssel-Erkenntnisse:**
- KFX Plugin ist kritische Abhängigkeit für Goodreads Integration
- Aktuelle Implementierung hat Plugin-Validierung als TODO markiert
- README.md fehlen spezifische KFX Plugin Installationsanweisungen
- CLI hat bereits System Requirements Check Framework, aber Plugin-Check nicht implementiert
- Test-Verzeichnis `/Volumes/Entertainment/Bücher/Calibre-Ingest` sollte in Dokumentation erwähnt werden

**Prioritäten:**
1. **HOCH**: README.md Dokumentation - Sofortige Hilfe für Benutzer
2. **MITTEL**: Plugin-Validierung implementieren - Bessere Fehlerbehandlung  
3. **NIEDRIG**: Interactive Plugin Installation - Nice-to-have Feature

**Architektur-Entscheidungen:**
- Plugin-Validierung in `FormatConverter` implementieren (nicht `KFXConverter`) für bessere Wiederverwendbarkeit
- System Requirements Check in `KFXConverter` erweitern
- Config Init sollte warnen aber nicht fehlschlagen bei fehlendem Plugin
- CLI Commands sollten Plugin-Check vor Conversion-Attempts durchführen

**Beziehung zu anderen Issues:**
- Issue #1 (BEHOBEN): ConfigManager Interface - ermöglicht bessere Plugin-Integration
- Issues #3, #4 (BEHOBEN): Grundlage für stabile Plugin-Implementierung vorhanden
- Issue #5 ist blockierend für Benutzer-Akzeptanz der KFX-Funktionalität

## Ressourcen & Referenzen

### Code-Dateien zur Bearbeitung
- **Hauptdokumentation**: `README.md` - Prerequisites und Troubleshooting Sections
- **Plugin-Validierung**: `src/calibre_books/core/converter.py` - `validate_kfx_plugin()` Implementierung
- **System Requirements**: `src/calibre_books/core/downloader.py` - `check_system_requirements()` Erweiterung
- **CLI Fehlerbehandlung**: `src/calibre_books/cli/convert.py` - KFX-spezifische Error Messages
- **Config Integration**: `src/calibre_books/cli/config.py` - Plugin-Warnung bei Init

### Plugin-Informationen
- **Plugin-Name**: "KFX Output"
- **Autor**: jhowell (offiziell)
- **Erkennungskommando**: `calibre-customize -l | grep KFX`
- **Erwartete Ausgabe**: `KFX Output (2, 17, 1) - Convert ebooks to KFX format`
- **Installation**: Calibre GUI → Preferences → Plugins → Get new plugins

### Test-Ressourcen
- **Test-Verzeichnis**: `/Volumes/Entertainment/Bücher/Calibre-Ingest`
- **Plugin-Mock-Strategien**: subprocess.run mocking für verschiedene Plugin-Status
- **Integration-Test-Szenarien**: Plugin vorhanden/fehlt/falsche Version

### Externe Referenzen
- **Calibre Plugin System**: https://manual.calibre-ebook.com/plugins.html
- **KFX Format Documentation**: Amazon Kindle Format spezifische Details
- **jhowell KFX Plugin**: Offizielle Referenz für Plugin-Installation

### Verwandte Scratchpads
- **Aktiv**: `2025-09-05_fix-kfx-config-manager-interface.md` - ConfigManager Interface für KFX
- **Abgeschlossen**: `2025-09-05_calibre-cli-tool-transformation.md` - CLI Architektur-Grundlage
- **Abgeschlossen**: `2025-09-06_asin-lookup-implementation.md` - ASIN Integration-Patterns

## Abschluss-Checkliste

### Dokumentation Erstellt und Erweitert
- [ ] README.md Prerequisites Section um KFX Plugin erweitert
- [ ] Schritt-für-Schritt Installationsanleitung für KFX Output Plugin hinzugefügt
- [ ] Plugin-Verfügbarkeits-Prüfung mit `calibre-customize -l | grep KFX` dokumentiert
- [ ] Troubleshooting Section um KFX Plugin Probleme erweitert
- [ ] Test-Verzeichnis `/Volumes/Entertainment/Bücher/Calibre-Ingest` in Dokumentation erwähnt

### Plugin-Validierung Implementiert
- [ ] `validate_kfx_plugin()` in `FormatConverter` vollständig implementiert
- [ ] Subprocess-basierte Plugin-Erkennung mit `calibre-customize -l`
- [ ] Regex-Pattern für KFX Output Plugin Erkennung
- [ ] Robuste Fehlerbehandlung für Plugin-Check-Failures
- [ ] Logging für Plugin-Validierung und Debugging

### CLI Integration und Fehlerbehandlung
- [ ] `check_system_requirements()` in `KFXConverter` um Plugin-Check erweitert
- [ ] KFX Conversion Commands prüfen Plugin vor Conversion-Attempts
- [ ] Hilfreiche Fehlermeldungen bei fehlendem KFX Plugin
- [ ] Config Init warnt bei fehlendem Plugin (ohne zu fehlschlagen)
- [ ] CLI Help-Text erwähnt KFX Plugin Anforderungen

### Testing und Validierung
- [ ] Unit-Tests für Plugin-Validierung geschrieben und bestanden
- [ ] Integration-Tests für KFX Conversion mit/ohne Plugin
- [ ] Error-Handling-Tests für verschiedene Plugin-Status-Szenarien
- [ ] Documentation-Tests für alle Links und Installation-Schritte
- [ ] User Experience Testing mit realem Test-Verzeichnis

### Code-Qualität und Standards  
- [ ] Alle Code-Änderungen folgen PEP8 Standards
- [ ] Type-Hints für alle neuen Funktionen hinzugefügt
- [ ] Logging-Standards befolgt (INFO, WARN, ERROR)
- [ ] Keine Breaking Changes in bestehender API
- [ ] Backward-Compatibility für alle Konfiguration-Optionen erhalten

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-06