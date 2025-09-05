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
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class ASINLookupService:
    """
    Multi-Source ASIN Lookup Service
    Implementiert verschiedene Strategien zur ASIN-Beschaffung
    """
    
    def __init__(self, cache_file="/tmp/asin_cache.json", rate_limit=2.0):
        self.cache_file = cache_file
        self.rate_limit = rate_limit  # Sekunden zwischen Anfragen
        self.cache = self.load_cache()
        
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
    
    def lookup_multiple_sources(self, isbn=None, title=None, author=None):
        """
        Hauptmethode: Sucht ASIN über mehrere Quellen
        """
        cache_key = f"{isbn}_{title}_{author}".lower()
        
        # Prüfe Cache zuerst
        if cache_key in self.cache:
            print(f"Cache-Treffer für {cache_key}")
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
                print(f"Versuche {method_name}...")
                asin = method()
                
                if asin and self.validate_asin(asin):
                    print(f"✓ ASIN gefunden via {method_name}: {asin}")
                    self.cache[cache_key] = asin
                    self.save_cache()
                    return asin
                
                # Rate Limiting
                time.sleep(self.rate_limit)
                
            except Exception as e:
                print(f"✗ Fehler bei {method_name}: {e}")
                continue
        
        print("Keine ASIN gefunden")
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
            print(f"Amazon Search Fehler: {e}")
        
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
    """Test der ASIN-Lookup Funktionalität"""
    
    lookup_service = ASINLookupService()
    
    # Test-Bücher
    test_books = [
        {
            'id': 'sturmlicht_1',
            'isbn': '9783641095949',
            'title': 'Der Weg der Könige', 
            'author': 'Brandon Sanderson'
        },
        {
            'id': 'sturmlicht_2', 
            'title': 'Words of Radiance',
            'author': 'Brandon Sanderson'
        }
    ]
    
    print("=== ASIN Lookup Test ===")
    
    for book in test_books:
        print(f"\nSuche ASIN für: {book['title']} von {book['author']}")
        
        asin = lookup_service.lookup_multiple_sources(
            isbn=book.get('isbn'),
            title=book['title'],
            author=book['author']
        )
        
        if asin:
            print(f"✓ Gefunden: {asin}")
        else:
            print("✗ Keine ASIN gefunden")
    
    # Batch-Test
    print(f"\n=== Batch Lookup Test ===")
    results = lookup_service.batch_lookup(test_books)
    
    print(f"Erfolgreich: {len(results['success'])}")
    print(f"Fehlgeschlagen: {len(results['failed'])}")
    print(f"Ergebnisse: {results['success']}")

if __name__ == "__main__":
    test_asin_lookup()