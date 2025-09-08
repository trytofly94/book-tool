# Feature Enhancement: Add support for more languages in ASIN lookup

**Erstellt**: 2025-09-08
**Typ**: Feature Enhancement
**Geschätzter Aufwand**: Mittel
**Verwandtes Issue**: GitHub #23 - Feature Enhancement: Add support for more languages in ASIN lookup

## Kontext & Ziel
Das ASIN-Lookup-System unterstützt aktuell 5 Sprachen (de, fr, es, it, en) mit entsprechenden Amazon-Domains. Issue #23 fordert die Erweiterung um mindestens 3 weitere Sprachen, prioritär Japanisch (ja), Portugiesisch (pt) und Niederländisch (nl). Das System ist bereits für diese Erweiterung architektiert.

**Aktuelle Unterstützung:**
- German (de) → amazon.de
- French (fr) → amazon.fr  
- Spanish (es) → amazon.es
- Italian (it) → amazon.it
- English (en) → amazon.com

**Ziel-Erweiterung:**
- Japanese (ja) → amazon.co.jp
- Portuguese (pt) → amazon.com.br
- Dutch (nl) → amazon.nl

## Anforderungen
- [ ] Mindestens 3 neue Sprachen implementieren (ja, pt, nl)
- [ ] Entsprechende Amazon-Domain-Mappings konfigurieren
- [ ] Titel-Pattern-Erkennung für neue Sprachen erweitern (falls nötig)
- [ ] Test-Coverage für neue Sprachen hinzufügen
- [ ] Dokumentation aktualisieren
- [ ] Real-World-Validierung mit Beispiel-Büchern

## Untersuchung & Analyse

### Prior Art Research
Aus der Analyse bestehender Scratchpads:
- **Issue #19**: Umfassendes Lokalisierungssystem bereits implementiert
- `LocalizationMetadataExtractor` Klasse vorhanden mit `language_mappings` Dictionary
- `enhanced_asin_lookup.py` unterstützt bereits sprachspezifische Amazon-Suche
- Architektur für Spracherweiterung optimal vorbereitet

### Aktuelle Implementierung (aus localization_metadata_extractor.py)
```python
self.language_mappings = {
    "de": {"name": "German", "amazon_domain": "amazon.de"},
    "fr": {"name": "French", "amazon_domain": "amazon.fr"},
    "es": {"name": "Spanish", "amazon_domain": "amazon.es"},
    "it": {"name": "Italian", "amazon_domain": "amazon.it"},
    "en": {"name": "English", "amazon_domain": "amazon.com"},
    "deu": {"name": "German", "amazon_domain": "amazon.de"},
    "eng": {"name": "English", "amazon_domain": "amazon.com"},
}
```

### Identifizierte Erweiterungspunkte
1. **LocalizationMetadataExtractor**: Hauptklasse für Sprachmappings
2. **enhanced_asin_lookup.py**: ASIN-Lookup-Service mit Lokalisierungsunterstützung
3. **Test-Suite**: `test_localization_comprehensive.py` für neue Sprachen erweitern
4. **CLI-Integration**: Menu-System für neue Sprachen testen

### Amazon-Domain-Recherche für Ziel-Sprachen
- **Japanese (ja)**: amazon.co.jp (bestätigt aktiv)
- **Portuguese (pt)**: amazon.com.br (Brasilien, größter portugiesischer Markt)
- **Dutch (nl)**: amazon.nl (seit 2020 verfügbar)
- **Medium Priority**: 
  - Chinese (zh) → amazon.cn
  - Korean (ko) → amazon.co.kr  
  - Swedish (sv) → amazon.se

## Implementierungsplan

### Phase 1: Core Language Mappings Extension
- [ ] Erweitern der `language_mappings` in `LocalizationMetadataExtractor`
- [ ] Hinzufügen der 3 prioritären Sprachen (ja, pt, nl)
- [ ] Alternative Sprachcodes hinzufügen (jpn→ja, por→pt, nld→nl)
- [ ] Validierung der Amazon-Domain-Verfügbarkeit

### Phase 2: Enhanced Pattern Recognition (falls erforderlich)
- [ ] Analyse: Benötigen die neuen Sprachen spezielle Titel-Pattern?
- [ ] Erweitern der `title_patterns` für bekannte Übersetzungen
- [ ] Implementierung character-set-spezifischer Behandlung (Japanisch, etc.)
- [ ] Fallback-Strategien für unbekannte Titel in neuen Sprachen

### Phase 3: ASIN Lookup Service Enhancement
- [ ] Testing der bestehenden `enhanced_asin_lookup.py` mit neuen Domains
- [ ] Sicherstellung dass User-Agents für internationale Amazon-Sites funktionieren
- [ ] Rate-Limiting für verschiedene internationale Amazon-Domains anpassen
- [ ] Fehlerbehandlung für domain-spezifische Blockierungen

### Phase 4: Comprehensive Testing
- [ ] Erweitern der Test-Suite um neue Sprachen
- [ ] Mock-Tests für Amazon-Domain-Responses erstellen
- [ ] Real-World-Testing mit Beispiel-Büchern:
  - Japanisches Buch: "ノルウェイの森" (Norwegian Wood) - Haruki Murakami
  - Portugiesisches Buch: "O Alquimista" (The Alchemist) - Paulo Coelho  
  - Niederländisches Buch: "Het Achterhuis" (Anne Frank Diary)
- [ ] Edge-Case-Testing: Mixed-language metadata, missing language codes

### Phase 5: CLI Integration & User Experience
- [ ] CLI-Menu um neue Sprachen erweitern
- [ ] Help-Text und Dokumentation aktualisieren
- [ ] Verbose-Mode-Output für neue Sprachen testen
- [ ] Error-Messages in verschiedenen Sprachen (optional)

### Phase 6: Documentation & Validation
- [ ] README-Update mit neuen unterstützten Sprachen
- [ ] Code-Comments für neue Sprachmappings
- [ ] Performance-Testing: Keine Regression bei bestehenden Sprachen
- [ ] Full-Pipeline-Test mit Test-Pfad `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline`

### Phase 7: Medium Priority Languages (optional)
- [ ] Chinese (zh) → amazon.cn (falls Zeit verfügbar)
- [ ] Korean (ko) → amazon.co.kr
- [ ] Swedish (sv) → amazon.se

## Technische Herausforderungen

### 1. Character Set Handling
- **Japanisch**: UTF-8 encoding, Hiragana/Katakana/Kanji-Unterstützung
- **Portugiesisch**: Akzente und Sonderzeichen (ã, ç, etc.)
- **Niederländisch**: Umlaute und Sonderzeichen (ij, etc.)
- Solution: Robust UTF-8 handling, URL-encoding für Suchanfragen

### 2. Amazon Domain Variations
- **Verschiedene HTML-Strukturen**: amazon.co.jp könnte andere Selektoren benötigen
- **Rate-Limiting**: Verschiedene Domains haben möglicherweise verschiedene Limits
- Solution: Domain-spezifische Scraping-Strategien, adaptive rate-limiting

### 3. Cultural Title Variations
- **Japanische Titel**: Können sowohl in Kanji als auch in lateinischer Schrift vorliegen
- **Portugiesische Titel**: Unterschiede zwischen brasilianischem und europäischem Portugiesisch
- Solution: Multiple search strategies, kulturspezifische Titel-Mappings

## Test-Strategie

### Unit Tests
```python
# Neue Test-Cases für language_mappings
def test_japanese_language_mapping():
    extractor = LocalizationMetadataExtractor()
    assert extractor.language_mappings["ja"]["amazon_domain"] == "amazon.co.jp"

def test_portuguese_language_mapping():
    extractor = LocalizationMetadataExtractor()
    assert extractor.language_mappings["pt"]["amazon_domain"] == "amazon.com.br"

def test_dutch_language_mapping():
    extractor = LocalizationMetadataExtractor()
    assert extractor.language_mappings["nl"]["amazon_domain"] == "amazon.nl"
```

### Integration Tests
- Real-World ASIN-Lookup-Tests für jede neue Sprache
- Performance-Tests: Keine Regression bei bestehenden Sprachen
- CLI-Tests: Neue Sprachen in Menu-System verfügbar

### Manual Validation
```bash
# Test-Commands für neue Sprachen
python3 calibre_asin_automation.py  # Menu Option 6: Test Japanese books
book-tool asin lookup --book "ノルウェイの森" --author "村上春樹" --verbose
book-tool asin lookup --book "O Alquimista" --author "Paulo Coelho" --verbose
book-tool asin lookup --book "Het Achterhuis" --author "Anne Frank" --verbose
```

## Akzeptanzkriterien (aus Issue #23)
- [ ] Mindestens 3 neue Sprachen implementiert (ja, pt, nl)
- [ ] Entsprechende Amazon-Domains konfiguriert
- [ ] Test-Coverage für neue Sprachen
- [ ] Dokumentation aktualisiert
- [ ] Real-World-Validierung mit Beispiel-Büchern

## Fortschrittsnotizen
*Wird während der Implementierung aktualisiert*

## Ressourcen & Referenzen
- GitHub Issue #23: https://github.com/[repo]/issues/23
- Bestehende Implementierung: `localization_metadata_extractor.py`
- ASIN-Lookup-Service: `enhanced_asin_lookup.py` 
- Test-Suite: `test_localization_comprehensive.py`
- Amazon International Domains:
  - https://amazon.co.jp (Japan)
  - https://amazon.com.br (Brazil/Portugal)  
  - https://amazon.nl (Netherlands)
- Related Issues:
  - Issue #19: Localization ASIN Lookup (completed)
  - Issue #18: ASIN Lookup API fixes (completed)

## Abschluss-Checkliste
- [ ] Kernfunktionalität implementiert (3+ neue Sprachen)
- [ ] Entsprechende Amazon-Domain-Mappings konfiguriert
- [ ] Tests geschrieben und bestanden für alle neuen Sprachen
- [ ] Real-World-Validierung mit internationalen Büchern durchgeführt
- [ ] Dokumentation aktualisiert (README, Code-Comments)
- [ ] CLI-Integration getestet (Menu-System, Help-Text)
- [ ] Performance-Validierung (keine Regression bei bestehenden Features)
- [ ] Code-Review durchgeführt (falls zutreffend)

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-08
**Architektur-Vorteil**: Bestehende Lokalisierungsarchitektur macht diese Erweiterung sehr straightforward
**Testdaten**: Testpfad `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline` verfügbar