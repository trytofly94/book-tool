# Fix ASIN Lookup API Failure - All title/author searches return no results

**Erstellt**: 2025-09-07
**Typ**: Bug Fix
**Geschätzter Aufwand**: Mittel
**Verwandtes Issue**: GitHub #18

## Kontext & Ziel

The primary ASIN lookup functionality in book-tool is completely broken for title/author searches. All queries return "No ASIN found from any source" regardless of the book or author tested, while ISBN-based searches work correctly. This is a critical bug that renders the main feature unusable.

## Anforderungen

- [ ] Diagnose why title/author ASIN lookups fail across all sources
- [ ] Fix Amazon search web scraping functionality
- [ ] Fix Google Books API integration for title/author queries
- [ ] Fix OpenLibrary API integration
- [ ] Verify network requests are properly formatted
- [ ] Ensure error handling doesn't mask actual failures
- [ ] Test with known working examples (Brandon Sanderson books, popular titles)
- [ ] Maintain backward compatibility with working ISBN lookups

## Untersuchung & Analyse

### Prior Art Research
- Completed scratchpads show that ASIN lookup was recently implemented in `2025-09-06_asin-lookup-implementation.md`
- The CLI tool has been fully restructured with pip-installable package in recent PRs #11-#14
- Current implementation uses multi-source approach: Amazon search, Google Books API, OpenLibrary API

### Current Architecture Analysis
Located in `src/calibre_books/core/asin_lookup.py`:

1. **ASINLookupService Class**: Main service with three lookup methods for title/author
   - `_lookup_via_amazon_search()`: Web scraping Amazon search results  
   - `_lookup_via_google_books()`: Using Google Books API v1
   - `_lookup_via_openlibrary()`: Using OpenLibrary API (ISBN-only currently)

2. **Issue Patterns Identified**:
   - Amazon search: BeautifulSoup parsing might be outdated for current Amazon HTML
   - Google Books: Query formatting may be incorrect for title/author searches
   - OpenLibrary: Currently only supports ISBN lookups in `_lookup_via_openlibrary()`
   - No verbose logging to debug actual API responses
   - Rate limiting might be interfering with debugging

3. **Working Components**:
   - ISBN-based lookups work (confirmed by issue reporter)
   - Cache system is functional
   - Network connectivity is working

## Implementierungsplan

### Phase 1: Diagnostic and Logging Enhancement
- [ ] Add comprehensive debug logging to all lookup methods
- [ ] Log actual HTTP requests and responses (sanitized)
- [ ] Add response status codes and content length logging
- [ ] Create debugging CLI flag for verbose ASIN lookup output

### Phase 2: Amazon Search Method Repair
- [ ] Update Amazon search URL format and parameters
- [ ] Review and fix BeautifulSoup selectors for current Amazon HTML structure
- [ ] Add fallback selectors for ASIN extraction
- [ ] Test with multiple User-Agent strings to avoid blocking
- [ ] Add retry mechanism with exponential backoff

### Phase 3: Google Books API Method Repair  
- [ ] Debug Google Books API query format for title/author searches
- [ ] Fix the query parameter encoding (`intitle:`, `inauthor:` format)
- [ ] Improve ASIN extraction from Google Books response identifiers
- [ ] Add better error handling for API rate limiting

### Phase 4: OpenLibrary Enhancement
- [ ] Extend OpenLibrary method to support title/author searches (not just ISBN)
- [ ] Add proper OpenLibrary Search API integration for book titles
- [ ] Implement ASIN extraction from OpenLibrary book records

### Phase 5: Integration Testing
- [ ] Create unit tests with mocked API responses
- [ ] Test with the specific examples from issue (Brandon Sanderson books)
- [ ] Test edge cases (special characters, international titles)
- [ ] Verify fallback behavior between sources
- [ ] Performance testing with rate limiting

### Phase 6: Error Handling and User Experience
- [ ] Improve error messages to be more specific about failures
- [ ] Add source-specific error reporting
- [ ] Implement graceful degradation when individual sources fail
- [ ] Update CLI output to show which sources were attempted

## Technische Herausforderungen

1. **Web Scraping Resilience**: Amazon frequently changes their HTML structure
   - Solution: Multiple selector strategies, regular testing
   
2. **API Rate Limiting**: Google Books and other APIs have usage limits
   - Solution: Proper rate limiting, retry with backoff, API key support
   
3. **Query Formatting**: Different APIs expect different query formats
   - Solution: Source-specific query builders, URL encoding

4. **False Negatives**: Methods might be working but returning empty results
   - Solution: Comprehensive logging to distinguish between "no results" and "method failed"

## Test-Strategie

### Manual Testing
```bash
# Test cases that should work after fix
book-tool asin lookup --book "The Way of Kings" --author "Brandon Sanderson" --verbose
book-tool asin lookup --book "Mistborn" --author "Brandon Sanderson" --verbose  
book-tool asin lookup --book "Dune" --author "Frank Herbert" --verbose
book-tool asin lookup --book "The Hobbit" --author "J.R.R. Tolkien" --verbose
```

### Unit Tests
- Mock HTTP responses for each API source
- Test query formatting for different title/author combinations
- Test error handling and fallback behavior
- Test ASIN validation and extraction

### Integration Tests  
- Live API testing with known good examples
- Performance testing with rate limiting
- Cache behavior verification

## Erwartete Ergebnisse

After implementation:
1. Title/author searches should successfully find ASINs for popular books
2. Each source should be properly tested and working
3. Clear error messages when legitimate failures occur
4. Comprehensive logging for debugging future issues
5. Maintained performance with proper rate limiting
6. ISBN lookups continue to work as before

## Fortschrittsnotizen

### Phase 1: Investigation Started
- Analyzed current ASIN lookup implementation architecture
- Identified three potential failure points in lookup methods
- Need to add comprehensive debugging to isolate the root cause

## Ressourcen & Referenzen

- Current Implementation: `src/calibre_books/core/asin_lookup.py`
- CLI Command: `src/calibre_books/cli/asin.py`
- Google Books API Documentation: https://developers.google.com/books/docs/v1/using
- OpenLibrary API Documentation: https://openlibrary.org/developers/api
- Amazon robots.txt: https://www.amazon.com/robots.txt (for scraping guidelines)

## Abschluss-Checkliste

- [ ] All three lookup sources (amazon, google-books, openlibrary) working for title/author searches
- [ ] Test cases pass with popular book examples 
- [ ] ISBN lookups continue to function correctly
- [ ] Comprehensive error handling and logging implemented
- [ ] User documentation updated with troubleshooting steps
- [ ] Unit tests written and passing
- [ ] Integration tests verify real API functionality

---
**Status**: Aktiv
**Zuletzt aktualisiert**: 2025-09-07