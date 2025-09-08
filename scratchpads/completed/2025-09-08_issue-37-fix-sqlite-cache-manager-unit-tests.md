# Issue #37: Fix failing unit tests for SQLiteCacheManager

**Erstellt**: 2025-09-08
**Typ**: Bug
**Geschätzter Aufwand**: Mittel
**Verwandtes Issue**: GitHub #37
**Test-Ordner**: /Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline

## Kontext & Ziel

Die Unit Tests für SQLiteCacheManager schlagen fehl, da sie versuchen, auf ein `cache_data` Attribut zuzugreifen, das in der SQLite-Implementierung nicht existiert. Die Tests wurden ursprünglich für einen JSON-basierten Cache Manager geschrieben, der ein `cache_data` Dictionary-Attribut hatte. Der neue SQLiteCacheManager verwendet stattdessen eine SQLite-Datenbank.

**Problem**: Tests erwarten eine JSON-ähnliche `cache_data` Schnittstelle, aber SQLiteCacheManager verwendet eine völlig andere SQLite-basierte Architektur.

**Ziel**: Alle SQLiteCacheManager Unit Tests funktionsfähig machen, ohne die bestehende SQLite-Implementierung zu beschädigen.

## Anforderungen

- [ ] Alle 9 derzeit fehlschlagenden SQLiteCacheManager Tests müssen bestehen
- [ ] Tests müssen SQLite-Datenbankoperationen korrekt validieren
- [ ] Thread-Sicherheit muss ordnungsgemäß mit SQLite getestet werden
- [ ] Keine Regression in bestehender Cache-Manager-Funktionalität
- [ ] Validierung mit echten Büchern aus Test-Ordner
- [ ] Kompatibilität mit SQLite WAL-Modus und Performance-Optimierungen

## Untersuchung & Analyse

### Prior Art Recherche

**Verwandte Scratchpads analysiert:**
- `2025-09-08_issue-34-unit-test-cache-manager-fix.md`: Zeigt erfolgreiche Lösung ähnlicher Import-Probleme
- `2025-09-08_pr35-code-review-cache-manager-fix.md`: Detaillierte Code-Review-Erkenntnisse zu Cache-Architektur

**Bestehende Arbeiten:**
- Issue #34 wurde bereits erfolgreich gelöst (CacheManager Import-Fehler behoben)
- PR #35 bietet Backward-Compatibility zwischen SQLite und JSON Cache Managern
- Umfassende Real-World-Validierung mit Brandon Sanderson Büchern bereits durchgeführt

### Aktuelle Testfehler-Analyse

**9 von 10 Tests schlagen fehl:**

1. **AttributeError: 'SQLiteCacheManager' object has no attribute 'cache_data'**
   - Betrifft: `test_cache_manager_init_new_cache`, `test_cache_manager_init_existing_cache`, `test_cache_thread_safety`, `test_cache_save_error_handling`, `test_cleanup_expired_stub`
   - Grund: Tests erwarten Dictionary `cache_data`, SQLiteCacheManager nutzt SQLite DB

2. **sqlite3.DatabaseError: file is not a database**
   - Betrifft: `test_cache_manager_init_existing_cache`, `test_cache_manager_corrupted_cache`
   - Grund: Tests erstellen JSON-Dateien, aber SQLiteCacheManager erwartet SQLite DB

3. **Cache-Datei-Format-Konflikt**
   - Betrifft: `test_cache_asin_and_get_cached_asin`
   - Grund: Test erstellt JSON-Datei, aber SQLite erwartet Datenbank

4. **Statistics-Format-Unterschied**
   - Betrifft: `test_cache_stats`
   - Grund: SQLite liefert `"4.0 KB"`, Test erwartet `" B"` Endung

### SQLiteCacheManager vs JSONCacheManager Interface-Unterschiede

**SQLiteCacheManager-Spezifische Eigenschaften:**
- Verwendet SQLite-Datenbank statt JSON-Datei
- Keine `cache_data` Dictionary-Eigenschaft
- TTL-basierte Ablaufzeiten mit automatischer Bereinigung
- WAL-Modus für bessere Concurrent Access
- Erweiterte Statistiken mit Quelle und Confidence Score
- Performance-Optimierungen (Indizierung, Memory Mapping)

**Gemeinsamkeiten beider Manager:**
- `cache_asin(key, asin)` - ASIN cachen
- `get_cached_asin(key)` - ASIN abrufen
- `clear()` - Cache leeren
- `get_stats()` - Statistiken abrufen
- `cleanup_expired()` - Abgelaufene Einträge bereinigen
- `close()` - Verbindungen schließen

## Implementierungsplan

### Phase 1: Test-Architektur-Analyse und -Design
- [ ] **Analysiere alle fehlschlagenden Tests**: Verstehe welche SQLite-spezifische Funktionalität getestet werden muss
- [ ] **Design SQLite-Test-Strategien**:
  - Temp SQLite-Dateien statt JSON für Tests
  - Mock-Strategien für Datenbankoperationen
  - Thread-Safety-Tests für SQLite WAL-Modus
- [ ] **Prüfe Kompatibilität mit Issue #34 Lösungen**: Stelle sicher, dass bestehende Backward-Compatibility nicht bricht

### Phase 2: Cache-Initialisierung-Tests reparieren
- [ ] **Fix test_cache_manager_init_new_cache**:
  - Entferne `cache_data` Assertions
  - Prüfe SQLite-Datenbank-Existenz und Schema
  - Validiere Performance-Optimierungen (WAL-Modus, Indizierung)
- [ ] **Fix test_cache_manager_init_existing_cache**:
  - Erstelle gültige SQLite-Datenbank statt JSON
  - Test Migration-Funktionalität von JSON zu SQLite
  - Prüfe Datenlese aus vorhandener SQLite-DB
- [ ] **Fix test_cache_manager_corrupted_cache**:
  - Erstelle korrupte SQLite-Datei statt JSON
  - Test graceful Wiederherstellung und Schema-Neuinitialisierung

### Phase 3: Core-Cache-Operationen reparieren
- [ ] **Fix test_cache_asin_and_get_cached_asin**:
  - Teste SQLite INSERT/SELECT-Operationen
  - Validiere TTL-Funktionalität und Expiration
  - Prüfe Source- und Confidence-Score-Metadaten
- [ ] **Fix test_cache_clear**:
  - Teste SQLite DELETE-Operationen
  - Validiere VACUUM-Operation für Space-Reclamation
  - Prüfe Statistics-Reset

### Phase 4: Erweiterte SQLite-Funktionalität testen
- [ ] **Fix test_cache_stats**:
  - Passe size_human Assertions an (KB statt B)
  - Teste erweiterte SQLite-Statistiken (Source Distribution, Top Entries)
  - Validiere Active vs Expired Entries Logic
- [ ] **Fix test_cache_thread_safety**:
  - Entferne `cache_data` direkte Zugriffe
  - Teste SQLite WAL-Modus Concurrent Access
  - Validiere Thread-sichere Operationen über SQL-Queries
- [ ] **Fix test_cleanup_expired_stub**:
  - Teste echte TTL-basierte Expiration Logic
  - Validiere SQLite-basierte Cleanup-Operationen
  - Prüfe VACUUM-Performance bei Large Cleanups

### Phase 5: Error-Handling und Edge-Cases
- [ ] **Fix test_cache_save_error_handling**:
  - Teste SQLite-spezifische Error-Scenarios (Locked DB, Disk Full)
  - Validiere Connection-Recovery und Retry-Logic
  - Prüfe Thread-Local Connection Handling

### Phase 6: Real-World-Validierung mit Test-Büchern
- [ ] **SQLite-Performance-Testing**: Test mit größerem Buchset aus Pipeline
  - Cache Hit/Miss Rate mit SQLite vs JSON
  - Memory Usage und Connection Pooling
  - TTL-basierte Expiration unter Load
- [ ] **Integration-Testing**: Vollständige CLI-Pipeline mit SQLite Cache
  - `calibre-books asin-lookup --cache-backend sqlite`
  - Multi-threaded Batch Processing Validation
  - Migration von JSON zu SQLite in produktionsähnlicher Umgebung

### Phase 7: Test-Infrastruktur-Verbesserungen
- [ ] **Erweitere Test-Coverage für SQLite-Features**:
  - Migration Testing (JSON→SQLite)
  - Backend-Switching Tests (SQLite↔JSON)
  - Performance Benchmarking Tests
- [ ] **Cleanup und Dokumentation**:
  - Aktualisiere Test-Docstrings für SQLite-Spezifika
  - Dokumentiere SQLite vs JSON Test-Unterschiede
  - Ensure proper test fixture cleanup (temp DB files)

## Testbücher für Validierung

### Priorisierte Test-Cases mit SQLite Cache
1. **Cache-Performance-Test**: `sanderson_elantris.epub`
   - Teste SQLite vs JSON Cache-Performance
   - Validiere TTL-basierte Expiration

2. **Concurrent-Access-Test**: Batch-Verarbeitung mit 5+ Büchern
   - SQLite WAL-Modus unter Multi-Threading Load
   - Connection Pooling und Thread-Safety

3. **Migration-Test**:
   - Beginne mit JSON Cache (aus vorherigen Tests)
   - Migriere zu SQLite und validiere Datenintegrität
   - Cache Hit Rate nach Migration

4. **Large-Dataset-Performance**:
   - Stormlight Archive Serie für SQLite Index-Performance
   - Source Distribution und Advanced Statistics

## Technische Herausforderungen

### SQLite vs JSON Test-Architektur
- **Problem**: Tests müssen SQLite-spezifische Eigenschaften validieren, aber kompatibel mit JSON bleiben
- **Lösungsansätze**:
  1. Separate Test-Classes für SQLite vs JSON
  2. Parameterisierte Tests für beide Backends
  3. Abstract Base Test Class mit Implementation-specific Tests

### Thread-Safety-Testing mit SQLite
- **SQLite WAL-Modus**: Tests müssen WAL-Mode Concurrent Access validieren
- **Connection Pooling**: Thread-Local Connections richtig testen
- **Lock-Verhalten**: SQLite-Locks vs JSON File-Locks

### TTL und Expiration Testing
- **Zeit-basierte Tests**: Reliable TTL-Testing ohne Race Conditions
- **Cleanup Performance**: VACUUM-Operations bei Large Datasets
- **Migration-Expiration**: JSON-Daten erhalten Default-TTL

## Anti-Overengineering Prinzipien

- **Minimal Test Changes**: Nur notwendige Änderungen für SQLite-Kompatibilität
- **Backend-Agnostic Interface**: Tests sollen Interface testen, nicht Implementation
- **Reuse Existing Patterns**: Nutze bewährte Patterns aus Issue #34 Lösung
- **Focused Test Scope**: Teste SQLite-Features nur wo sie sich von JSON unterscheiden

## Fortschrittsnotizen

[Platz für Implementierungsfortschritt und Erkenntnisse während der Entwicklung]

## Ressourcen & Referenzen

- **GitHub Issue**: #37 "Fix failing unit tests for SQLiteCacheManager"
- **Related Issues**: #34 (CacheManager Import Fix - ✅ Gelöst)
- **Related PR**: #35 (Cache Manager Backward Compatibility)
- **Cache-Implementation**: `src/calibre_books/core/cache.py`
- **Test-File**: `tests/unit/test_asin_lookup.py` (Zeilen 576-754)
- **Test-Bücher**: `/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/`
- **Successful Prior Art**: Issue #34 Scratchpad für bewährte Patterns

## Abschluss-Checkliste

- [ ] Alle 9 fehlschlagenden SQLiteCacheManager Tests bestehen
- [ ] Tests validieren SQLite-Datenbankoperationen korrekt
- [ ] Thread-Sicherheit ordnungsgemäß mit SQLite WAL-Modus getestet
- [ ] Keine Regression in bestehender Cache-Manager-Funktionalität
- [ ] Real-World-Validierung mit Testbüchern abgeschlossen
- [ ] TTL-basierte Expiration Logic vollständig getestet
- [ ] Migration von JSON zu SQLite funktioniert einwandfrei
- [ ] Performance-Unterschiede zwischen SQLite und JSON dokumentiert
- [ ] Code-Quality-Checks bestanden
- [ ] Integration-Tests mit CLI erfolgreich
- [ ] Documentation bei Test-Änderungen aktualisiert

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-08
**Geschätzte Entwicklungszeit**: 4-6 Stunden
**Branch**: Wird erstellt als `fix/issue-37-sqlite-cache-manager-tests`
