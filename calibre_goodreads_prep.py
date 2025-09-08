#!/usr/bin/env python3
"""
Automatische Vorbereitung von eBooks für Goodreads-Integration
Fügt ASINs hinzu und konvertiert zu KFX-Format
"""

import subprocess
import os
import re
import requests

def get_amazon_asin(title, author=None):
    """
    Versucht, die Amazon ASIN für ein Buch zu finden
    """
    try:
        # Erstelle Suchquery
        query = title
        if author:
            query = f"{title} {author}"
        
        # Amazon-Suche (vereinfacht - in Realität sollte man die Amazon API verwenden)
        search_url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}&i=digital-text"
        
        print(f"Suche Amazon ASIN für: {query}")
        
        # Hinweis: Dies ist ein vereinfachtes Beispiel
        # In der Praxis sollten Sie die offizielle Amazon API verwenden
        # oder ein robusteres Web-Scraping mit Proxies/Headers implementieren
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers)
        
        if response.status_code == 200:
            # Suche nach ASIN in der Antwort
            asin_pattern = r'/dp/([B][A-Z0-9]{9})'
            matches = re.findall(asin_pattern, response.text)
            
            if matches:
                return matches[0]  # Erste gefundene ASIN
        
        return None
        
    except Exception as e:
        print(f"Fehler bei ASIN-Suche: {e}")
        return None

def add_asin_to_calibre_book(book_path, asin):
    """
    Fügt ASIN zu einem Calibre-Buch hinzu
    """
    try:
        # Verwende Calibre's ebook-meta Tool
        cmd = [
            "ebook-meta", book_path, 
            "--identifier", f"amazon:{asin}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✓ ASIN {asin} zu {os.path.basename(book_path)} hinzugefügt")
            return True
        else:
            print(f"✗ Fehler beim Hinzufügen der ASIN: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Fehler beim Bearbeiten der Metadaten: {e}")
        return False

def convert_to_kfx(input_path, output_path):
    """
    Konvertiert ein eBook zu KFX-Format für Goodreads-Integration
    """
    try:
        # Verwende Calibre's ebook-convert
        cmd = [
            "ebook-convert", input_path, output_path,
            "--output-profile", "kindle_fire",
            "--no-inline-toc"
        ]
        
        print(f"Konvertiere zu KFX: {os.path.basename(input_path)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✓ Erfolgreich zu KFX konvertiert: {os.path.basename(output_path)}")
            return True
        else:
            print(f"✗ Konvertierungsfehler: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"Konvertierungsfehler: {e}")
        return False

def process_books_for_goodreads(directory):
    """
    Verarbeitet alle Bücher in einem Verzeichnis für Goodreads-Integration
    """
    supported_formats = ['.mobi', '.epub', '.azw3']
    processed_books = []
    
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        if not os.path.isfile(file_path):
            continue
            
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext in supported_formats:
            print(f"\n--- Verarbeite: {filename} ---")
            
            # Extrahiere Titel aus Dateinamen (vereinfacht)
            title = os.path.splitext(filename)[0].replace('_', ' ')
            
            # Versuche ASIN zu finden (in Realität sollten Sie manuelle Eingabe/Konfiguration verwenden)
            # asin = get_amazon_asin(title)
            # 
            # if asin:
            #     # Füge ASIN hinzu
            #     add_asin_to_calibre_book(file_path, asin)
            
            # Für jetzt: Benutzer-Eingabe für ASIN
            print(f"Bitte geben Sie die Amazon ASIN für '{title}' ein:")
            print("(Finden Sie diese auf der Amazon Kindle Store Seite)")
            asin = input("ASIN (beginnt mit 'B'): ").strip()
            
            if asin and asin.startswith('B') and len(asin) == 10:
                add_asin_to_calibre_book(file_path, asin)
                
                # Konvertiere zu KFX
                kfx_filename = os.path.splitext(filename)[0] + '_goodreads.azw3'
                kfx_path = os.path.join(directory, kfx_filename)
                
                if convert_to_kfx(file_path, kfx_path):
                    processed_books.append({
                        'original': filename,
                        'kfx': kfx_filename,
                        'asin': asin
                    })
            else:
                print(f"⚠ Ungültige ASIN für {filename}, überspringe...")
    
    return processed_books

def main():
    directory = "/Volumes/Entertainment/Bücher/Calibre-Ingest"
    
    if not os.path.exists(directory):
        print(f"Verzeichnis nicht gefunden: {directory}")
        return
    
    print("=== Calibre Goodreads Integration Vorbereitung ===")
    print("Dieses Skript:")
    print("1. Fügt Amazon ASINs zu eBook Metadaten hinzu")
    print("2. Konvertiert Bücher zu KFX-Format für Goodreads-Integration")
    print("3. Bereitet Bücher für USB-Transfer zum Kindle vor")
    print()
    
    processed = process_books_for_goodreads(directory)
    
    if processed:
        print("\n=== Zusammenfassung ===")
        print("Erfolgreich verarbeitet:")
        for book in processed:
            print(f"  • {book['original']} → {book['kfx']} (ASIN: {book['asin']})")
        
        print(f"\n✓ {len(processed)} Bücher bereit für Kindle!")
        print("\nNächste Schritte:")
        print("1. Verbinden Sie Ihren Kindle per USB")
        print("2. Übertragen Sie die *_goodreads.azw3 Dateien zum Kindle")
        print("3. Löschen Sie alte Versionen der Bücher vom Kindle")
        print("4. Testen Sie die Goodreads-Integration")
    else:
        print("\n⚠ Keine Bücher wurden verarbeitet")

if __name__ == "__main__":
    main()