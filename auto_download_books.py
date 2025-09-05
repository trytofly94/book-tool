#!/usr/bin/env python3
"""
Automatisierter Book Download mit Librarian CLI
"""

import subprocess
import os
import json
import sys

# Konfiguration
DOWNLOAD_PATH = "/Volumes/Entertainment/Bücher/Calibre-Ingest"
PREFERRED_FORMAT = "mobi"  # oder "epub"

def search_and_download_series(author, series_name, preferred_format="mobi"):
    """
    Sucht und lädt eine komplette Buchserie herunter
    """
    print(f"Suche nach: {author} {series_name}")
    
    # Suche nach der Serie
    search_query = f"{author} {series_name} {preferred_format}"
    
    try:
        # Führe die Suche aus
        result = subprocess.run([
            "librarian", "-p", DOWNLOAD_PATH, "search", search_query
        ], capture_output=True, text=True, check=True)
        
        print("Suche abgeschlossen, lade search_results.json...")
        
        # Lade die Suchergebnisse
        with open(os.path.join(DOWNLOAD_PATH, "search_results.json"), "r") as f:
            results = json.load(f)
        
        # Filtere nach gewünschtem Format
        mobi_books = [book for book in results if book["format"].upper() == preferred_format.upper()]
        
        print(f"Gefunden: {len(mobi_books)} Bücher im {preferred_format.upper()} Format")
        
        # Download der Bücher
        for i, book in enumerate(mobi_books):
            title = book["title"]
            hash_id = book["hash"]
            
            # Erstelle sauberen Dateinamen
            safe_filename = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_filename = safe_filename.replace(' ', '_') + f".{preferred_format}"
            
            print(f"Lade herunter ({i+1}/{len(mobi_books)}): {title}")
            
            try:
                subprocess.run([
                    "librarian", "download", hash_id, safe_filename
                ], cwd=DOWNLOAD_PATH, check=True)
                
                # Bewege von Downloads zum Zielordner falls nötig
                downloads_path = f"/Users/{os.getenv('USER')}/Downloads/{safe_filename}"
                target_path = os.path.join(DOWNLOAD_PATH, safe_filename)
                
                if os.path.exists(downloads_path):
                    subprocess.run(["mv", downloads_path, target_path], check=True)
                    print(f"✓ Erfolgreich heruntergeladen: {safe_filename}")
                else:
                    print(f"⚠ Datei nicht im Downloads-Ordner gefunden: {safe_filename}")
                    
            except subprocess.CalledProcessError as e:
                print(f"✗ Fehler beim Download von {title}: {e}")
                continue
                
    except subprocess.CalledProcessError as e:
        print(f"Fehler bei der Suche: {e}")
        return False
    except FileNotFoundError:
        print("search_results.json nicht gefunden")
        return False
    except json.JSONDecodeError:
        print("Fehler beim Laden der Suchergebnisse")
        return False
    
    return True

def main():
    if len(sys.argv) < 3:
        print("Usage: python auto_download_books.py '<author>' '<series>' [format]")
        print("Beispiel: python auto_download_books.py 'Brandon Sanderson' 'Sturmlicht' mobi")
        sys.exit(1)
    
    author = sys.argv[1]
    series = sys.argv[2]
    format_pref = sys.argv[3] if len(sys.argv) > 3 else PREFERRED_FORMAT
    
    # Stelle sicher, dass der Zielordner existiert
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    
    success = search_and_download_series(author, series, format_pref)
    
    if success:
        print(f"\n✓ Download abgeschlossen! Dateien befinden sich in: {DOWNLOAD_PATH}")
    else:
        print("\n✗ Download fehlgeschlagen")

if __name__ == "__main__":
    main()