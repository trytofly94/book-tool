# ASIN-Lookup Kernfunktionalität implementieren

**Erstellt**: 2025-09-06
**Typ**: Bug/Feature
**Geschätzter Aufwand**: Mittel-Groß
**Verwandtes Issue**: GitHub #3

## Kontext & Ziel
Das book-tool CLI bewirbt ASIN-Lookup als Kernfunktionalität, aber die aktuelle Implementierung in `src/calibre_books/core/asin_lookup.py` ist nur ein Stub, der "Not implemented yet" zurückgibt. Users können keine ASINs für ihre Bücher finden, was die gesamte Metadata-Pipeline bricht und das Tool praktisch unbrauchbar macht.

Das Ziel ist es, die fehlende ASIN-Lookup-Funktionalität zu implementieren, indem die vorhandene `enhanced_asin_lookup.py` in die neue CLI-Architektur integriert wird.

## Anforderungen
- [ ] ASIN-Lookup über Multiple Sources (Amazon, Goodreads, OpenLibrary)
- [ ] Unterstützung für Titel + Autor und ISBN-basierte Suche
- [ ] Cache-Management für Performance und Rate-Limiting-Respekt
- [ ] Integration mit dem bestehenden CLI-Interface (asin lookup)
- [ ] Robuste Fehlerbehandlung und Logging
- [ ] Batch-Update-Funktionalität für Calibre-Libraries
- [ ] ASIN-Validierung und Availability-Checking
- [ ] Konfigurierbare Rate-Limits und Sources
- [ ] Progress-Reporting für langwierige Operations

## Untersuchung & Analyse

### Prior Art Analysis
1. **Enhanced ASIN Lookup (enhanced_asin_lookup.py)**:
   - ✅ Vollständig implementierte Multi-Source-Lookup-Funktionalität
   - ✅ Unterstützt Amazon Direct Search, Google Books, OpenLibrary
   - ✅ Robuste Caching-Mechanismen
   - ✅ Batch-Processing mit Rate-Limiting
   - ✅ Selenium-basierte Browser-Automatisierung für komplexe Suchen
   - ⚠️ Nicht in die neue CLI-Architektur integriert
   - ⚠️ Verwendet alte Pfad-Struktur (/tmp/asin_cache.json)

2. **Current CLI Implementation (asin_lookup.py)**:
   - ✅ Vollständige CLI-Interface bereits definiert
   - ✅ Korrekte Integration mit Configuration Management
   - ✅ Progress-Management und Rich-Console-Output
   - ✅ Proper Error-Handling und Context-Management
   - ❌ Alle Core-Methods sind Stubs ("Not implemented yet")

### Architecture Gap Analysis
Die bestehende enhanced_asin_lookup.py implementiert die gesamte Lookup-Logic, aber:
- Verwendet veraltete Pfad-Konventionen
- Nicht in die Pydantic-basierte Configuration integriert
- Verwendet print() statt proper Logging
- Inkompatible Datenstrukturen mit der neuen ASINLookupResult-Klasse

## Implementierungsplan

### Phase 1: Core Service Integration
- [ ] enhanced_asin_lookup.py Funktionalität in ASINLookupService übertragen
- [ ] Multi-Source-Lookup-Methods implementieren:
  - [ ] lookup_by_title() - Titel + Autor basierte Suche
  - [ ] lookup_by_isbn() - ISBN-basierte Suche
  - [ ] Validate_asin() - ASIN-Format-Validierung
- [ ] Cache-Management mit konfigurierbaren Pfaden integrieren
- [ ] Rate-Limiting und Request-Throttling implementieren

### Phase 2: Data Structure Alignment
- [ ] ASINLookupResult-Klasse erweitern für Metadata und Source-Info
- [ ] BookMetadata-Integration für reichhaltigere Metadaten
- [ ] Configuration-Schema für ASIN-Sources und Rate-Limits
- [ ] Progress-Callback-Integration für alle Lookup-Methods

### Phase 3: Advanced Features
- [ ] batch_update() für Multi-Book-Processing implementieren
- [ ] check_availability() für ASIN-Verification
- [ ] Selenium-Integration für erweiterte Amazon-Suchen
- [ ] Cache-Statistics und Management-Commands
- [ ] Multi-Threading für Batch-Operations

### Phase 4: Quality & Testing
- [ ] Comprehensive Unit-Tests für alle Lookup-Methods
- [ ] Integration-Tests mit echten API-Calls (mockable)
- [ ] Error-Handling für Network-Timeouts und Rate-Limiting
- [ ] Logging-Integration statt print-Statements
- [ ] Documentation-Update für neue Funktionalität

### Phase 5: CLI Integration & Validation
- [ ] Ende-zu-Ende-Tests mit dem Test-Directory /Volumes/Entertainment/Bücher/Calibre-Ingest
- [ ] Performance-Optimierung für große Bibliotheken
- [ ] Configuration-Validation und User-Guidance
- [ ] Error-Messages und Help-Text-Verbesserungen

## Technische Details

### Sources Priority Order
1. **ISBN-Direct**: Amazon ISBN-Redirect (fastest, most reliable)
2. **Amazon-Search**: Web-Scraping von Suchergebnissen
3. **Google-Books**: API-basierte Suche mit Fallback
4. **OpenLibrary**: API-basierte Suche (selten ASINs)
5. **Selenium-Amazon**: Browser-Automatisierung als letzte Option

### Cache Strategy
- JSON-basierter Cache im ~/.book-tool/ Directory
- Cache-Keys: Normalisierte "isbn_title_author" Strings
- Configurable TTL (default: 7 days für erfolgreiche Lookups)
- Separate Cache-Entries für unterschiedliche Sources
- Cache-Cleanup und Statistics-Commands

### Rate Limiting
- Configurable per-source Rate-Limits (default: 2 seconds)
- Exponential Backoff bei HTTP 429 Responses
- Respect robots.txt und User-Agent Best-Practices
- Batch-Processing mit Staggered-Requests

### Error Handling
- Graceful Degradation bei Source-Failures
- Retry-Logic mit Exponential-Backoff
- Network-Timeout-Handling
- User-Friendly Error-Messages

## Fortschrittsnotizen
- Issue #3 analysiert: Critical Bug, ASIN-Lookup komplett nicht implementiert
- Bestehende enhanced_asin_lookup.py identifiziert als vollständige Funktionalität-Source
- CLI-Interface in asin.py ist bereits vollständig spezifiziert aber nicht implementiert
- Architecture-Gap zwischen Old-System und New-CLI identifiziert
- Implementierungsplan in 5 Phasen strukturiert

## Ressourcen & Referenzen
- [GitHub Issue #3](https://github.com/user/book-tool/issues/3)
- enhanced_asin_lookup.py: Vollständige Multi-Source-Implementation
- src/calibre_books/cli/asin.py: CLI-Interface-Spezifikation
- src/calibre_books/core/asin_lookup.py: Stub-Implementation zum Ersetzen
- Test-Directory: /Volumes/Entertainment/Bücher/Calibre-Ingest

## Risiko-Assessment
- **Medium Risk**: Web-Scraping von Amazon kann instabil sein (Lösung: Selenium-Fallback)
- **Low Risk**: API-Rate-Limits bei Google Books (Lösung: Built-in Rate-Limiting)
- **Medium Risk**: Cache-Corruption bei parallelen Zugriffen (Lösung: File-Locking)
- **High Impact**: Erfolgreiche Implementierung macht tool vollständig funktionsfähig

## Abschluss-Checkliste
- [ ] lookup_by_title() und lookup_by_isbn() vollständig implementiert
- [ ] Cache-Management mit konfigurierbaren Pfaden funktioniert
- [ ] Batch-Update für Calibre-Libraries erfolgreich
- [ ] CLI-Commands funktionieren mit echten ASIN-Lookups
- [ ] Tests bestehen und Coverage ist ausreichend
- [ ] Dokumentation reflektiert neue Funktionalität
- [ ] End-to-End-Test mit /Volumes/Entertainment/Bücher/Calibre-Ingest erfolgreich
- [ ] Issue #3 kann als resolved markiert werden

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-06
