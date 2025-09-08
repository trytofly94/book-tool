#!/usr/bin/env python3
"""
Calibre ASIN Automation mit Custom Columns
Implementiert die Recherche-Erkenntnisse für automatisiertes ASIN-Management
"""

import subprocess
import os
import json
import sys

class CalibreASINAutomation:
    """
    Automatisiertes ASIN-Management für Calibre
    Basierend auf der Recherche zu Calibre CLI-Integration
    """
    
    def __init__(self, library_path=None):
        self.library_path = library_path
        self.setup_calibre_environment()
        
        # Importiere Enhanced ASIN Lookup und Localization Support
        sys.path.append(os.path.dirname(__file__))
        try:
            from enhanced_asin_lookup import ASINLookupService
            self.lookup_service = ASINLookupService()
            print("✓ Enhanced ASIN Lookup Service initialized with localization support")
        except ImportError:
            print("⚠ Enhanced ASIN Lookup nicht verfügbar")
            self.lookup_service = None
        
        # Import Localization Metadata Extractor
        try:
            from localization_metadata_extractor import LocalizationMetadataExtractor
            self.localization_extractor = LocalizationMetadataExtractor()
            print("✓ Localization Metadata Extractor initialized")
        except ImportError:
            print("⚠ Localization Metadata Extractor nicht verfügbar")
            self.localization_extractor = None
    
    def setup_calibre_environment(self):
        """Setup für Calibre CLI Environment"""
        # Stelle sicher, dass Calibre CLI Tools verfügbar sind
        if not self.check_calibre_availability():
            self.install_calibre_if_needed()
    
    def check_calibre_availability(self):
        """Prüft ob Calibre CLI Tools verfügbar sind"""
        tools = ['calibredb', 'ebook-convert', 'ebook-meta']
        
        for tool in tools:
            try:
                result = subprocess.run([tool, '--version'], 
                                      capture_output=True, text=True)
                if result.returncode != 0:
                    return False
            except FileNotFoundError:
                return False
        
        return True
    
    def install_calibre_if_needed(self):
        """Installiert Calibre falls nicht vorhanden"""
        print("Calibre nicht gefunden. Installation erforderlich:")
        print("macOS: brew install --cask calibre")
        print("Linux: sudo apt install calibre")
        print("Windows: Download von https://calibre-ebook.com/")
        return False
    
    def get_base_cmd(self):
        """Erstellt Basis-Kommando mit Library-Pfad"""
        cmd = ['calibredb']
        if self.library_path:
            cmd.extend(['--library-path', self.library_path])
        return cmd
    
    def create_asin_custom_column(self):
        """
        Erstellt Custom Column für ASIN in Calibre
        Basierend auf: calibredb add_custom_column asin "Amazon ASIN" text
        """
        try:
            cmd = self.get_base_cmd() + [
                'add_custom_column',
                'asin',
                'Amazon ASIN',
                'text',
                '--display', '{"description": "Amazon ASIN für Goodreads Integration"}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✓ ASIN Custom Column erstellt")
                return True
            elif "already exists" in result.stderr.lower():
                print("ℹ ASIN Custom Column existiert bereits")
                return True
            else:
                print(f"✗ Fehler beim Erstellen der Custom Column: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Fehler beim Erstellen der Custom Column: {e}")
            return False
    
    def list_books_without_asin(self, limit=None):
        """
        Listet Bücher ohne ASIN auf
        """
        try:
            cmd = self.get_base_cmd() + ['list', '--fields', 'id,title,authors,#asin']
            
            if limit:
                cmd.extend(['--limit', str(limit)])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                books_without_asin = []
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                
                for line in lines:
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 4:
                            book_id, title, authors, asin = parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else ""
                            
                            # Prüfe ob ASIN fehlt oder leer ist
                            if not asin or asin.strip() == "":
                                books_without_asin.append({
                                    'id': book_id,
                                    'title': title,
                                    'authors': authors
                                })
                
                return books_without_asin
        
        except Exception as e:
            print(f"Fehler beim Auflisten der Bücher: {e}")
        
        return []
    
    def set_asin_for_book(self, book_id, asin):
        """
        Setzt ASIN für ein spezifisches Buch
        Basierend auf: calibredb set_custom asin 123 "B01234567X"
        """
        try:
            cmd = self.get_base_cmd() + [
                'set_custom',
                'asin',
                str(book_id),
                asin
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True
            else:
                print(f"✗ Fehler beim Setzen der ASIN für Buch {book_id}: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Fehler beim Setzen der ASIN: {e}")
            return False
    
    def batch_update_asins(self, asin_mapping):
        """
        Batch-Update für mehrere ASINs
        asin_mapping: {book_id: asin_value}
        """
        success_count = 0
        total_count = len(asin_mapping)
        
        print(f"Batch-Update für {total_count} Bücher...")
        
        for book_id, asin in asin_mapping.items():
            if self.set_asin_for_book(book_id, asin):
                success_count += 1
                print(f"✓ ASIN gesetzt für Buch {book_id}: {asin}")
            else:
                print(f"✗ Fehlgeschlagen für Buch {book_id}")
        
        print(f"Batch-Update abgeschlossen: {success_count}/{total_count} erfolgreich")
        return success_count
    
    def get_book_identifiers(self, book_id):
        """Holt vorhandene Identifiers für ein Buch"""
        try:
            cmd = self.get_base_cmd() + ['show_metadata', str(book_id)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                metadata = {}
                for line in result.stdout.split('\n'):
                    if 'Identifiers' in line:
                        # Parse Identifiers Line
                        identifiers_str = line.split(':', 1)[1].strip()
                        # Format: isbn:123456, amazon:B123456
                        for identifier in identifiers_str.split(','):
                            if ':' in identifier:
                                key, value = identifier.strip().split(':', 1)
                                metadata[key] = value
                        break
                
                return metadata
        
        except Exception as e:
            print(f"Fehler beim Abrufen der Identifiers: {e}")
        
        return {}
    
    def get_book_file_path(self, book_id):
        """
        Get the file path of a book in the Calibre library for localization metadata extraction
        """
        try:
            cmd = self.get_base_cmd() + ['list', '--fields', 'path', '--search', f'id:{book_id}']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # Skip header, get path
                if len(lines) > 1 and lines[1].strip():
                    relative_path = lines[1].strip()
                    
                    # Construct full path
                    if self.library_path:
                        full_path = os.path.join(self.library_path, relative_path)
                    else:
                        # Use default Calibre library location
                        default_library = os.path.expanduser("~/Calibre Library")
                        full_path = os.path.join(default_library, relative_path)
                    
                    # Look for common book file formats in the directory
                    if os.path.exists(full_path):
                        for filename in os.listdir(full_path):
                            if filename.lower().endswith(('.epub', '.mobi', '.azw', '.azw3', '.pdf')):
                                book_file_path = os.path.join(full_path, filename)
                                print(f"  Gefunden: {filename}")
                                return book_file_path
        
        except Exception as e:
            print(f"Fehler beim Abrufen des Dateipfads für Buch {book_id}: {e}")
        
        return None
    
    def process_book_files_direct_asin(self, book_files, dry_run=False):
        """
        Direct ASIN lookup for book files (not in Calibre library yet)
        Useful for testing localization with files in pipeline directories
        
        Args:
            book_files: List of file paths to books
            dry_run: If True, don't perform actual lookups
        """
        if not self.lookup_service:
            print("✗ ASIN Lookup Service nicht verfügbar")
            return {}
        
        print("=== Direct Book Files ASIN Lookup ===")
        print(f"Processing {len(book_files)} book files with localization support...")
        
        asin_results = {}
        
        for book_file in book_files:
            if not os.path.exists(book_file):
                print(f"\n✗ Datei nicht gefunden: {book_file}")
                continue
            
            filename = os.path.basename(book_file)
            print(f"\n{'='*50}")
            print(f"Verarbeite: {filename}")
            print(f"{'='*50}")
            
            if not dry_run:
                # Use enhanced lookup with localization
                asin = self.lookup_service.lookup_multiple_sources(file_path=book_file)
                
                if asin:
                    asin_results[filename] = asin
                    print(f"✓ ASIN gefunden: {asin}")
                else:
                    print("✗ Keine ASIN gefunden")
            else:
                print(f"[DRY RUN] Würde ASIN suchen für: {filename}")
        
        # Summary
        print(f"\n{'='*50}")
        print("=== Zusammenfassung ===")
        if not dry_run:
            print(f"ASINs gefunden: {len(asin_results)}")
            print(f"Fehlgeschlagen: {len(book_files) - len(asin_results)}")
            if asin_results:
                print("\nGefundene ASINs:")
                for filename, asin in asin_results.items():
                    print(f"  {filename}: {asin}")
        else:
            print(f"Würde {len(book_files)} Dateien verarbeiten")
        
        return asin_results
    
    def process_library_automatic_asin(self, max_books=None, dry_run=False):
        """
        Automatische ASIN-Beschaffung für die gesamte Bibliothek
        """
        if not self.lookup_service:
            print("✗ ASIN Lookup Service nicht verfügbar")
            return
        
        print("=== Automatische ASIN-Beschaffung ===")
        
        # 1. Custom Column erstellen
        self.create_asin_custom_column()
        
        # 2. Bücher ohne ASIN finden
        books_without_asin = self.list_books_without_asin(limit=max_books)
        
        if not books_without_asin:
            print("✓ Alle Bücher haben bereits ASINs")
            return
        
        print(f"Gefunden: {len(books_without_asin)} Bücher ohne ASIN")
        
        # 3. Für jedes Buch ASIN suchen
        asin_updates = {}
        
        for book in books_without_asin:
            book_id = book['id']
            title = book['title']
            authors = book['authors']
            
            print(f"\nVerarbeite: {title} von {authors}")
            
            # Hole vorhandene Identifiers (für ISBN)
            identifiers = self.get_book_identifiers(book_id)
            isbn = identifiers.get('isbn')
            
            if isbn:
                print(f"  ISBN gefunden: {isbn}")
            
            # Enhanced ASIN-Lookup with Localization Support
            if not dry_run:
                # Try to get book file path for localization
                book_file_path = self.get_book_file_path(book_id)
                
                if book_file_path and self.localization_extractor:
                    print(f"  Verwende Lokalisierung für: {os.path.basename(book_file_path)}")
                    # Use localized lookup with file path
                    asin = self.lookup_service.lookup_multiple_sources(
                        isbn=isbn,
                        title=title,
                        author=authors,
                        file_path=book_file_path
                    )
                else:
                    print(f"  Verwende Standard-Lookup (Datei nicht verfügbar)")
                    # Fallback to standard lookup
                    asin = self.lookup_service.lookup_multiple_sources(
                        isbn=isbn,
                        title=title,
                        author=authors
                    )
                
                if asin:
                    asin_updates[book_id] = asin
                    print(f"  ✓ ASIN gefunden: {asin}")
                else:
                    print(f"  ✗ Keine ASIN gefunden")
            else:
                print(f"  [DRY RUN] Würde ASIN suchen für: {title}")
        
        # 4. Batch-Update durchführen
        if asin_updates and not dry_run:
            success_count = self.batch_update_asins(asin_updates)
            print(f"\n=== Zusammenfassung ===")
            print(f"ASINs erfolgreich gesetzt: {success_count}")
            print(f"Bücher ohne ASIN: {len(books_without_asin) - success_count}")
        elif dry_run:
            print(f"\n=== Dry Run Zusammenfassung ===")
            print(f"Würde {len(books_without_asin)} Bücher verarbeiten")
        
        return asin_updates
    
    def export_library_asin_status(self, output_file=None):
        """Exportiert ASIN-Status der gesamten Bibliothek"""
        if not output_file:
            output_file = "library_asin_status.json"
        
        try:
            cmd = self.get_base_cmd() + ['list', '--fields', 'id,title,authors,#asin,identifiers']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                library_status = {
                    'books': [],
                    'statistics': {
                        'total_books': 0,
                        'books_with_asin': 0,
                        'books_without_asin': 0
                    }
                }
                
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                
                for line in lines:
                    if line.strip():
                        parts = line.split('\t')
                        if len(parts) >= 4:
                            book_id, title, authors = parts[0], parts[1], parts[2]
                            asin = parts[3] if len(parts) > 3 else ""
                            identifiers = parts[4] if len(parts) > 4 else ""
                            
                            has_asin = bool(asin and asin.strip())
                            
                            library_status['books'].append({
                                'id': book_id,
                                'title': title,
                                'authors': authors,
                                'asin': asin,
                                'identifiers': identifiers,
                                'has_asin': has_asin
                            })
                            
                            library_status['statistics']['total_books'] += 1
                            if has_asin:
                                library_status['statistics']['books_with_asin'] += 1
                            else:
                                library_status['statistics']['books_without_asin'] += 1
                
                # Speichere in Datei
                with open(output_file, 'w') as f:
                    json.dump(library_status, f, indent=2, ensure_ascii=False)
                
                print(f"✓ Bibliotheks-Status exportiert: {output_file}")
                print(f"  Bücher gesamt: {library_status['statistics']['total_books']}")
                print(f"  Mit ASIN: {library_status['statistics']['books_with_asin']}")
                print(f"  Ohne ASIN: {library_status['statistics']['books_without_asin']}")
                
                return library_status
        
        except Exception as e:
            print(f"Fehler beim Exportieren des Bibliotheks-Status: {e}")
        
        return None

def main():
    """Hauptfunktion für Calibre ASIN Automation"""
    print("=== Calibre ASIN Automation ===")
    
    # Bibliotheks-Pfad bestimmen
    default_library = os.path.expanduser("~/Calibre Library")
    
    if os.path.exists(default_library):
        library_path = default_library
        print(f"Verwende Standard-Bibliothek: {library_path}")
    else:
        print("Standard Calibre Library nicht gefunden.")
        library_path = input("Pfad zur Calibre Library (leer für Standard): ").strip()
        if not library_path:
            library_path = None
    
    # Automation initialisieren
    automation = CalibreASINAutomation(library_path)
    
    # Menü
    while True:
        print("\n=== Optionen ===")
        print("1. ASIN Custom Column erstellen")
        print("2. Bücher ohne ASIN auflisten")
        print("3. Automatische ASIN-Beschaffung (Dry Run)")
        print("4. Automatische ASIN-Beschaffung (Live)")
        print("5. Bibliotheks-Status exportieren")
        print("6. Test Localization mit German Books")
        print("7. Beenden")
        
        choice = input("Auswahl (1-7): ").strip()
        
        if choice == "1":
            automation.create_asin_custom_column()
        
        elif choice == "2":
            books = automation.list_books_without_asin(limit=20)
            print(f"\nBücher ohne ASIN ({len(books)}):")
            for book in books[:10]:
                print(f"  ID {book['id']}: {book['title']} - {book['authors']}")
            if len(books) > 10:
                print(f"  ... und {len(books) - 10} weitere")
        
        elif choice == "3":
            automation.process_library_automatic_asin(max_books=5, dry_run=True)
        
        elif choice == "4":
            max_books = input("Max. Anzahl Bücher (leer für alle): ").strip()
            max_books = int(max_books) if max_books else None
            automation.process_library_automatic_asin(max_books=max_books, dry_run=False)
        
        elif choice == "5":
            automation.export_library_asin_status()
        
        elif choice == "6":
            # Test localization with German books
            test_files = [
                '/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/sanderson_mistborn1_kinder-des-nebels.epub',
                '/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/sanderson_skyward1_ruf-der-sterne.epub',
                '/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/sanderson_mistborn2_krieger-des-feuers.epub',
            ]
            
            # Filter existing files
            existing_files = [f for f in test_files if os.path.exists(f)]
            
            if existing_files:
                print(f"Testing mit {len(existing_files)} deutschen Büchern...")
                dry_run_choice = input("Dry Run? (y/n): ").strip().lower() == 'y'
                automation.process_book_files_direct_asin(existing_files, dry_run=dry_run_choice)
            else:
                print("Keine Test-Dateien verfügbar in:")
                for f in test_files:
                    print(f"  {f}")
        
        elif choice == "7":
            break
        
        else:
            print("Ungültige Auswahl")

if __name__ == "__main__":
    main()