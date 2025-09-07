#!/usr/bin/env python3
"""
Erweiterte ASIN-Lookup Klasse mit mehreren Quellen
Basierend auf der Recherche zu automatisierter Goodreads-Integration
"""

import requests
import time
import re
import json
import os
import sys
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Import our localization metadata extractor
try:
    from localization_metadata_extractor import LocalizationMetadataExtractor
except ImportError:
    LocalizationMetadataExtractor = None
    print("Warning: LocalizationMetadataExtractor not available. Localization features disabled.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ASINLookupService:
    """
    Multi-Source ASIN Lookup Service
    Implementiert verschiedene Strategien zur ASIN-Beschaffung
    """
    
    def __init__(self, cache_file="/tmp/asin_cache.json", rate_limit=2.0):
        self.cache_file = cache_file
        self.rate_limit = rate_limit  # Sekunden zwischen Anfragen
        self.cache = self.load_cache()
        
        # Initialize localization support
        self.localization_extractor = LocalizationMetadataExtractor() if LocalizationMetadataExtractor else None
        
        # User Agents für Web Scraping
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        ]
    
    def load_cache(self):
        """Lädt ASIN-Cache aus Datei"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_cache(self):
        """Speichert ASIN-Cache in Datei"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Cache-Speicherfehler: {e}")
    
    def lookup_multiple_sources(self, isbn=None, title=None, author=None, file_path=None):
        """
        Hauptmethode: Sucht ASIN über mehrere Quellen
        Enhanced with localization support for non-English books
        
        Args:
            isbn: ISBN of the book
            title: Title of the book (can be localized)
            author: Author name
            file_path: Path to book file for metadata extraction
        """
        # If file_path is provided, extract localized metadata
        if file_path and self.localization_extractor:
            logger.info(f"Extracting localized metadata from: {file_path}")
            metadata = self.localization_extractor.extract_metadata_from_path(file_path)
            
            # Use extracted metadata if available, otherwise fall back to provided values
            if metadata.get('title'):
                title = metadata['title']
                logger.info(f"Using extracted title: {title}")
            if metadata.get('author'):
                author = metadata['author']
            
            # Generate localized search terms
            search_terms = self.localization_extractor.get_localized_search_terms(metadata)
            
            # Try localized searches first
            for search_term in search_terms:
                logger.info(f"Trying localized search: {search_term['title']} ({search_term['language']}) on {search_term['amazon_domain']}")
                asin = self.lookup_with_localized_terms(search_term, isbn)
                if asin:
                    return asin
        
        # Fallback to standard lookup
        return self.lookup_standard_sources(isbn, title, author)
    
    def lookup_with_localized_terms(self, search_term, isbn=None):
        """
        Perform ASIN lookup with localized search terms
        """
        title = search_term['title']
        author = search_term['author']
        amazon_domain = search_term['amazon_domain']
        language = search_term['language']
        
        cache_key = f"{isbn}_{title}_{author}_{language}".lower()
        
        # Check cache first
        if cache_key in self.cache:
            logger.info(f"Cache hit for localized search: {cache_key}")
            return self.cache[cache_key]
        
        # Try localized Amazon search
        try:
            asin = self.lookup_via_amazon_search_localized(title, author, amazon_domain)
            if asin and self.validate_asin(asin):
                logger.info(f"✓ ASIN found via localized Amazon search ({language}): {asin}")
                self.cache[cache_key] = asin
                self.save_cache()
                return asin
        except Exception as e:
            logger.error(f"Error in localized Amazon search: {e}")
        
        # Rate limiting
        time.sleep(self.rate_limit)
        return None
    
    def lookup_standard_sources(self, isbn=None, title=None, author=None):
        """
        Standard ASIN lookup methods (fallback)
        """
        cache_key = f"{isbn}_{title}_{author}".lower()
        
        # Prüfe Cache zuerst
        if cache_key in self.cache:
            logger.info(f"Cache hit for standard search: {cache_key}")
            return self.cache[cache_key]
        
        # Methoden in Prioritätsreihenfolge
        lookup_methods = [
            ('ISBN-Direct', lambda: self.lookup_by_isbn_direct(isbn) if isbn else None),
            ('Amazon-Search', lambda: self.lookup_via_amazon_search(title, author)),
            ('Google-Books', lambda: self.lookup_via_google_books(isbn, title, author)),
            ('OpenLibrary', lambda: self.lookup_via_openlibrary(isbn) if isbn else None),
        ]
        
        for method_name, method in lookup_methods:
            try:
                logger.info(f"Trying {method_name}...")
                asin = method()
                
                if asin and self.validate_asin(asin):
                    logger.info(f"✓ ASIN found via {method_name}: {asin}")
                    self.cache[cache_key] = asin
                    self.save_cache()
                    return asin
                
                # Rate Limiting
                time.sleep(self.rate_limit)
                
            except Exception as e:
                logger.error(f"✗ Error in {method_name}: {e}")
                continue
        
        logger.info("No ASIN found")
        return None
    
    def validate_asin(self, asin):
        """Validiert ASIN-Format"""
        if not asin:
            return False
        return bool(re.match(r'^B[A-Z0-9]{9}$', asin.upper()))
    
    def lookup_by_isbn_direct(self, isbn):
        """
        Direkte ISBN-zu-ASIN Konvertierung über Amazon
        """
        if not isbn:
            return None
        
        # Bereinige ISBN
        clean_isbn = re.sub(r'[^0-9X]', '', isbn.upper())
        
        try:
            # Amazon ISBN-Redirect versuchen
            url = f"https://www.amazon.com/dp/{clean_isbn}"
            headers = {'User-Agent': self.user_agents[0]}
            
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
            
            if response.status_code == 200:
                # Suche ASIN in der finalen URL
                final_url = response.url
                asin_match = re.search(r'/dp/([B][A-Z0-9]{9})', final_url)
                
                if asin_match:
                    return asin_match.group(1)
            
        except Exception as e:
            print(f"ISBN-Direct Lookup Fehler: {e}")
        
        return None
    
    def lookup_via_amazon_search(self, title, author):
        """
        Web Scraping von Amazon-Suchergebnissen
        WARNUNG: Rechtliche Grauzone, verwende sparsam!
        """
        if not title:
            return None
        
        try:
            # Erstelle Suchquery
            query = title
            if author:
                query = f"{title} {author}"
            
            query = query.replace(' ', '+')
            url = f"https://www.amazon.com/s?k={query}&i=digital-text"
            
            headers = {'User-Agent': self.user_agents[0]}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Suche nach Produkten mit data-asin Attribut
                products = soup.find_all(attrs={'data-asin': True})
                
                for product in products:
                    asin = product.get('data-asin')
                    if asin and asin.startswith('B'):
                        return asin
        
        except Exception as e:
            logger.error(f"Amazon Search Fehler: {e}")
        
        return None
    
    def lookup_via_amazon_search_localized(self, title, author, amazon_domain):
        """
        Localized Amazon search using specific Amazon domain
        Enhanced version that searches on country-specific Amazon sites
        
        Args:
            title: Book title (localized)
            author: Author name
            amazon_domain: Amazon domain (e.g., amazon.de, amazon.fr)
        """
        if not title:
            return None
        
        try:
            # Erstelle Suchquery
            query = title
            if author:
                query = f"{title} {author}"
            
            query = query.replace(' ', '+')
            
            # Use the specified Amazon domain
            if amazon_domain == 'amazon.de':
                url = f"https://www.amazon.de/s?k={query}&i=digital-text"
            elif amazon_domain == 'amazon.fr':
                url = f"https://www.amazon.fr/s?k={query}&i=digital-text"
            elif amazon_domain == 'amazon.es':
                url = f"https://www.amazon.es/s?k={query}&i=digital-text"
            elif amazon_domain == 'amazon.it':
                url = f"https://www.amazon.it/s?k={query}&i=digital-text"
            else:
                # Default to amazon.com
                url = f"https://www.amazon.com/s?k={query}&i=digital-text"
            
            headers = {'User-Agent': self.user_agents[0]}
            logger.info(f"Searching {amazon_domain} for: {query}")
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Suche nach Produkten mit data-asin Attribut
                products = soup.find_all(attrs={'data-asin': True})
                
                for product in products:
                    asin = product.get('data-asin')
                    if asin and asin.startswith('B'):
                        logger.info(f"Found ASIN {asin} on {amazon_domain}")
                        return asin
            else:
                logger.warning(f"Amazon search returned status {response.status_code}")
        
        except Exception as e:
            logger.error(f"Localized Amazon Search Error on {amazon_domain}: {e}")
        
        return None
    
    def lookup_via_selenium(self, title, author):
        """
        Selenium-basierte Amazon-Suche (robuster aber langsamer)
        """
        if not title:
            return None
        
        try:
            # Chrome Options für Headless-Betrieb
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"--user-agent={self.user_agents[0]}")
            
            # WebDriver initialisieren
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Suche durchführen
            query = title
            if author:
                query = f"{title} {author}"
            
            url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}&i=digital-text"
            driver.get(url)
            
            # Warte auf Laden
            time.sleep(3)
            
            # Suche nach Produkten mit data-asin
            products = driver.find_elements(By.CSS_SELECTOR, '[data-asin]')
            
            for product in products:
                asin = product.get_attribute('data-asin')
                if asin and asin.startswith('B'):
                    driver.quit()
                    return asin
            
            driver.quit()
            
        except Exception as e:
            print(f"Selenium Lookup Fehler: {e}")
        
        return None
    
    def lookup_via_google_books(self, isbn, title, author):
        """
        Google Books API für ISBN/Titel-Lookup
        """
        try:
            # Erstelle Suchquery
            query_parts = []
            if isbn:
                query_parts.append(f"isbn:{isbn}")
            if title:
                query_parts.append(f'intitle:"{title}"')
            if author:
                query_parts.append(f'inauthor:"{author}"')
            
            if not query_parts:
                return None
            
            query = '+'.join(query_parts)
            url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=5"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get('items', []):
                    volume_info = item.get('volumeInfo', {})
                    industry_identifiers = volume_info.get('industryIdentifiers', [])
                    
                    # Suche nach ASIN in den Identifiern
                    for identifier in industry_identifiers:
                        if identifier.get('type') == 'OTHER':
                            asin_candidate = identifier.get('identifier', '')
                            if self.validate_asin(asin_candidate):
                                return asin_candidate
        
        except Exception as e:
            print(f"Google Books Lookup Fehler: {e}")
        
        return None
    
    def lookup_via_openlibrary(self, isbn):
        """
        Open Library API für ISBN-Lookup
        """
        if not isbn:
            return None
        
        try:
            clean_isbn = re.sub(r'[^0-9X]', '', isbn.upper())
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Open Library hat selten ASINs, aber versuche es
                for book_data in data.values():
                    identifiers = book_data.get('identifiers', {})
                    
                    # Suche nach Amazon-Identifiern
                    amazon_ids = identifiers.get('amazon', [])
                    for amazon_id in amazon_ids:
                        if self.validate_asin(amazon_id):
                            return amazon_id
        
        except Exception as e:
            print(f"OpenLibrary Lookup Fehler: {e}")
        
        return None
    
    def batch_lookup(self, books_data, max_workers=3):
        """
        Batch-Processing für mehrere Bücher
        books_data: Liste von Dicts mit 'isbn', 'title', 'author' Keys
        """
        import concurrent.futures
        import threading
        
        results = {}
        failed = []
        
        def lookup_single(book_data):
            book_id = book_data.get('id', f"{book_data.get('title', '')}_{book_data.get('author', '')}")
            
            try:
                asin = self.lookup_multiple_sources(
                    isbn=book_data.get('isbn'),
                    title=book_data.get('title'),
                    author=book_data.get('author')
                )
                
                if asin:
                    results[book_id] = asin
                else:
                    failed.append(book_id)
                    
            except Exception as e:
                print(f"Batch-Lookup Fehler für {book_id}: {e}")
                failed.append(book_id)
        
        # Parallel processing mit Rate Limiting
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            for book_data in books_data:
                future = executor.submit(lookup_single, book_data)
                futures.append(future)
                
                # Stagger requests to respect rate limits
                time.sleep(self.rate_limit / max_workers)
            
            # Warte auf alle Futures
            concurrent.futures.wait(futures)
        
        return {
            'success': results,
            'failed': failed,
            'total_processed': len(books_data)
        }

def test_asin_lookup():
    """Test der ASIN-Lookup Funktionalität mit Lokalisierung"""
    
    lookup_service = ASINLookupService()
    
    print("=== Enhanced ASIN Lookup Test with Localization ===")
    
    # Test with actual German book file
    test_file = '/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/sanderson_mistborn1_kinder-des-nebels.epub'
    
    if os.path.exists(test_file):
        print(f"\n=== Testing with real German book file ===")
        print(f"File: {os.path.basename(test_file)}")
        
        # Test localized lookup
        asin = lookup_service.lookup_multiple_sources(file_path=test_file)
        
        if asin:
            print(f"✓ ASIN found: {asin}")
        else:
            print("✗ No ASIN found")
    
    else:
        print(f"Test file not found: {test_file}")
        print("Continuing with manual test cases...")
    
    # Test-Bücher für manuellen Test
    test_books = [
        {
            'id': 'mistborn_german',
            'title': 'Kinder des Nebels',
            'author': 'Brandon Sanderson',
            'expected_language': 'de'
        },
        {
            'id': 'mistborn_english',
            'title': 'Mistborn',
            'author': 'Brandon Sanderson',
            'expected_language': 'en'
        },
        {
            'id': 'stormlight_german',
            'title': 'Der Weg der Könige',
            'author': 'Brandon Sanderson',
            'expected_language': 'de'
        }
    ]
    
    print("\n=== Manual Test Cases ===")
    
    for book in test_books:
        print(f"\nTesting: {book['title']} by {book['author']} ({book['expected_language']})")
        
        # Test standard lookup (for comparison)
        asin = lookup_service.lookup_standard_sources(
            title=book['title'],
            author=book['author']
        )
        
        if asin:
            print(f"✓ ASIN found via standard lookup: {asin}")
        else:
            print("✗ No ASIN found via standard lookup")
        
        print("-" * 50)
    
    print("\n=== Test completed ===")
    print("Note: For full localization testing, ensure the test EPUB file is available.")

if __name__ == "__main__":
    test_asin_lookup()