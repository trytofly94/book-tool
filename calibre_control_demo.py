#!/usr/bin/env python3
"""
Demonstration der Calibre-Kontrolle via Kommandozeile
"""

import subprocess
import os
import json

def list_calibre_tools():
    """
    Zeigt alle verfügbaren Calibre Kommandozeilen-Tools
    """
    calibre_tools = [
        'calibre',           # GUI starten
        'calibredb',         # Bibliothek verwalten
        'ebook-convert',     # Format-Konvertierung
        'ebook-meta',        # Metadaten bearbeiten
        'ebook-edit',        # eBook Editor
        'fetch-ebook-metadata',  # Metadaten von Online-Quellen
        'lrf2lrs',           # LRF zu LRS konvertieren
        'lrs2lrf',           # LRS zu LRF konvertieren
        'calibre-server',    # Content Server starten
        'calibre-smtp',      # Email-Versand
        'web2disk',          # Website zu eBook
    ]
    
    print("=== Verfügbare Calibre Kommandozeilen-Tools ===")
    for tool in calibre_tools:
        try:
            result = subprocess.run([tool, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                print(f"✓ {tool:<20} - {version}")
            else:
                print(f"✗ {tool:<20} - Nicht verfügbar")
        except FileNotFoundError:
            print(f"✗ {tool:<20} - Nicht installiert")

def demonstrate_calibredb():
    """
    Zeigt calibredb Funktionen (Bibliothek-Verwaltung)
    """
    print("\n=== CalibreDB Beispiele ===")
    
    # Standard Bibliothek-Pfad ermitteln
    try:
        result = subprocess.run(['calibredb', 'list_categories'], capture_output=True, text=True)
        print("Verfügbare Kategorien in der Bibliothek:")
        print(result.stdout)
    except:
        print("Keine Standard-Bibliothek gefunden")
    
    # Beispiele für calibredb Befehle
    examples = {
        'Liste alle Bücher': 'calibredb list',
        'Zeige Buch-Details': 'calibredb show_metadata 1',
        'Füge Buch hinzu': 'calibredb add /path/to/book.mobi',
        'Exportiere Buch': 'calibredb export 1 /path/to/export/',
        'Suche Bücher': 'calibredb list -s "title:Sturmlicht"',
        'Setze Metadaten': 'calibredb set_metadata 1 --field title:"Neuer Titel"',
        'Entferne Buch': 'calibredb remove 1',
        'Import von Verzeichnis': 'calibredb add --recurse /path/to/books/',
    }
    
    for description, command in examples.items():
        print(f"{description}:")
        print(f"  {command}\n")

def demonstrate_ebook_convert():
    """
    Zeigt ebook-convert Funktionen
    """
    print("=== eBook-Convert Beispiele ===")
    
    examples = {
        'MOBI zu EPUB': 'ebook-convert input.mobi output.epub',
        'EPUB zu KFX (Kindle)': 'ebook-convert input.epub output.azw3 --output-profile kindle_fire',
        'Mit Metadaten': 'ebook-convert input.mobi output.epub --title "Neuer Titel" --authors "Autor Name"',
        'PDF zu EPUB': 'ebook-convert input.pdf output.epub --pdf-engine poppler',
        'Batch-Konvertierung': 'for file in *.mobi; do ebook-convert "$file" "${file%.mobi}.epub"; done',
    }
    
    for description, command in examples.items():
        print(f"{description}:")
        print(f"  {command}\n")

def demonstrate_ebook_meta():
    """
    Zeigt ebook-meta Funktionen
    """
    print("=== eBook-Meta Beispiele ===")
    
    examples = {
        'Metadaten anzeigen': 'ebook-meta book.mobi',
        'Titel setzen': 'ebook-meta book.mobi --title "Neuer Titel"',
        'Autor setzen': 'ebook-meta book.mobi --authors "Autor Name"',
        'ASIN hinzufügen': 'ebook-meta book.mobi --identifier amazon:B123456789',
        'Cover setzen': 'ebook-meta book.mobi --cover cover.jpg',
        'Mehrere Felder': 'ebook-meta book.mobi --title "Titel" --authors "Autor" --tags "Fantasy,Roman"',
        'JSON Export': 'ebook-meta book.mobi --get-cover cover.jpg --to-json metadata.json',
    }
    
    for description, command in examples.items():
        print(f"{description}:")
        print(f"  {command}\n")

def practical_calibre_automation():
    """
    Praktisches Beispiel für Calibre-Automatisierung
    """
    print("=== Praktisches Automatisierungs-Beispiel ===")
    
    automation_script = '''
# Beispiel-Workflow für automatisierte Buchverarbeitung

# 1. Alle MOBI-Dateien in einem Ordner verarbeiten
for book in *.mobi; do
    echo "Verarbeite: $book"
    
    # Metadaten extrahieren
    ebook-meta "$book" > "${book%.mobi}_metadata.txt"
    
    # ASIN hinzufügen (falls vorhanden)
    # ebook-meta "$book" --identifier amazon:B123456789
    
    # Zu EPUB konvertieren
    ebook-convert "$book" "${book%.mobi}.epub" \\
        --output-profile generic_eink \\
        --margin-left 5 --margin-right 5 \\
        --margin-top 5 --margin-bottom 5
    
    # Zu KFX für Kindle konvertieren
    ebook-convert "$book" "${book%.mobi}_kindle.azw3" \\
        --output-profile kindle_fire \\
        --no-inline-toc
done

# 2. Bücher zur Calibre-Bibliothek hinzufügen
calibredb add *.epub --recurse

# 3. Metadaten automatisch vervollständigen
calibredb list | grep -o "^[0-9]*" | while read id; do
    fetch-ebook-metadata --identifier isbn:$(calibredb show_metadata $id | grep -o "isbn:[^]]*")
done

# 4. Backup der Bibliothek
calibredb backup_metadata backup.json
    '''
    
    print(automation_script)

def create_calibre_wrapper():
    """
    Erstellt einen Python-Wrapper für häufige Calibre-Operationen
    """
    wrapper_code = '''
class CalibreController:
    """
    Python-Wrapper für Calibre-Operationen
    """
    
    def __init__(self, library_path=None):
        self.library_path = library_path
        self.base_cmd = ['calibredb']
        if library_path:
            self.base_cmd.extend(['--library-path', library_path])
    
    def add_book(self, file_path, metadata=None):
        """Fügt ein Buch zur Bibliothek hinzu"""
        cmd = self.base_cmd + ['add', file_path]
        if metadata:
            for key, value in metadata.items():
                cmd.extend([f'--{key}', value])
        
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def list_books(self, search=None, fields=None):
        """Listet Bücher in der Bibliothek"""
        cmd = self.base_cmd + ['list']
        if search:
            cmd.extend(['-s', search])
        if fields:
            cmd.extend(['--fields', fields])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else None
    
    def get_metadata(self, book_id):
        """Holt Metadaten für ein Buch"""
        cmd = self.base_cmd + ['show_metadata', str(book_id)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else None
    
    def set_metadata(self, book_id, field, value):
        """Setzt Metadaten für ein Buch"""
        cmd = self.base_cmd + ['set_metadata', str(book_id), 
                               '--field', f'{field}:{value}']
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def convert_book(self, input_path, output_path, options=None):
        """Konvertiert ein Buch zwischen Formaten"""
        cmd = ['ebook-convert', input_path, output_path]
        if options:
            for key, value in options.items():
                cmd.extend([f'--{key}', str(value)])
        
        return subprocess.run(cmd, capture_output=True, text=True)
    
    def search_books(self, query):
        """Durchsucht die Bibliothek"""
        return self.list_books(search=query)

# Verwendungsbeispiel:
# calibre = CalibreController('/path/to/library')
# calibre.add_book('/path/to/book.mobi', {'title': 'Mein Buch'})
# books = calibre.search_books('title:Sturmlicht')
'''
    
    with open('/Volumes/Entertainment/Bücher/Calibre-Ingest/calibre_controller.py', 'w') as f:
        f.write(wrapper_code)
    
    print("Python-Wrapper erstellt: calibre_controller.py")

def main():
    print("=== Calibre-Kontrolle Demonstration ===\n")
    
    # Zeige verfügbare Tools
    list_calibre_tools()
    
    # Zeige Verwendungsbeispiele
    demonstrate_calibredb()
    demonstrate_ebook_convert() 
    demonstrate_ebook_meta()
    
    # Praktisches Beispiel
    practical_calibre_automation()
    
    # Erstelle Python-Wrapper
    create_calibre_wrapper()

if __name__ == "__main__":
    main()