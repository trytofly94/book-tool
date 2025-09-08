#!/usr/bin/env python3
"""
Direkter Zugriff auf die Calibre-Datenbank (SQLite)
WARNUNG: Nur für Experten, kann Bibliothek beschädigen!
"""

import sqlite3
import os
from datetime import datetime

class CalibreDatabaseController:
    """
    Direkter Zugriff auf Calibre-Datenbank
    VORSICHT: Kann die Bibliothek beschädigen!
    """
    
    def __init__(self, library_path):
        self.library_path = library_path
        self.db_path = os.path.join(library_path, "metadata.db")
        
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Calibre-Datenbank nicht gefunden: {self.db_path}")
    
    def connect(self):
        """Verbindung zur Datenbank"""
        return sqlite3.connect(self.db_path)
    
    def backup_database(self, backup_path=None):
        """Erstellt Backup der Datenbank"""
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.library_path, f"metadata_backup_{timestamp}.db")
        
        import shutil
        shutil.copy2(self.db_path, backup_path)
        return backup_path
    
    def get_books(self, limit=None, search_title=None):
        """
        Liest Bücher aus der Datenbank
        """
        with self.connect() as conn:
            query = """
                SELECT 
                    books.id,
                    books.title,
                    books.sort,
                    books.timestamp,
                    books.path,
                    authors.name as author
                FROM books
                LEFT JOIN books_authors_link ON books.id = books_authors_link.book
                LEFT JOIN authors ON books_authors_link.author = authors.id
            """
            
            params = []
            
            if search_title:
                query += " WHERE books.title LIKE ?"
                params.append(f"%{search_title}%")
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor = conn.execute(query, params)
            books = []
            
            for row in cursor.fetchall():
                books.append({
                    'id': row[0],
                    'title': row[1],
                    'sort': row[2],
                    'timestamp': row[3],
                    'path': row[4],
                    'author': row[5]
                })
            
            return books
    
    def get_book_formats(self, book_id):
        """Holt alle verfügbaren Formate für ein Buch"""
        with self.connect() as conn:
            cursor = conn.execute("""
                SELECT format, name, uncompressed_size 
                FROM data 
                WHERE book = ?
            """, (book_id,))
            
            formats = []
            for row in cursor.fetchall():
                formats.append({
                    'format': row[0],
                    'filename': row[1],
                    'size': row[2]
                })
            
            return formats
    
    def get_book_identifiers(self, book_id):
        """Holt alle Identifier (ASINs, ISBNs, etc.) für ein Buch"""
        with self.connect() as conn:
            cursor = conn.execute("""
                SELECT type, val 
                FROM identifiers 
                WHERE book = ?
            """, (book_id,))
            
            identifiers = {}
            for row in cursor.fetchall():
                identifiers[row[0]] = row[1]
            
            return identifiers
    
    def set_book_identifier(self, book_id, identifier_type, value):
        """
        Setzt einen Identifier für ein Buch
        VORSICHT: Direkte Datenbankmanipulation!
        """
        with self.connect() as conn:
            # Prüfe ob Identifier bereits existiert
            cursor = conn.execute("""
                SELECT id FROM identifiers 
                WHERE book = ? AND type = ?
            """, (book_id, identifier_type))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update bestehenden Identifier
                conn.execute("""
                    UPDATE identifiers 
                    SET val = ? 
                    WHERE book = ? AND type = ?
                """, (value, book_id, identifier_type))
            else:
                # Füge neuen Identifier hinzu
                conn.execute("""
                    INSERT INTO identifiers (book, type, val) 
                    VALUES (?, ?, ?)
                """, (book_id, identifier_type, value))
            
            conn.commit()
            return True
    
    def search_books_by_metadata(self, **kwargs):
        """
        Erweiterte Buchsuche nach verschiedenen Metadaten
        """
        query_parts = ["SELECT DISTINCT books.id, books.title FROM books"]
        joins = []
        conditions = []
        params = []
        
        # Autor-Suche
        if 'author' in kwargs:
            joins.append("LEFT JOIN books_authors_link ON books.id = books_authors_link.book")
            joins.append("LEFT JOIN authors ON books_authors_link.author = authors.id")
            conditions.append("authors.name LIKE ?")
            params.append(f"%{kwargs['author']}%")
        
        # Tag-Suche
        if 'tag' in kwargs:
            joins.append("LEFT JOIN books_tags_link ON books.id = books_tags_link.book")
            joins.append("LEFT JOIN tags ON books_tags_link.tag = tags.id")
            conditions.append("tags.name LIKE ?")
            params.append(f"%{kwargs['tag']}%")
        
        # Serie-Suche
        if 'series' in kwargs:
            joins.append("LEFT JOIN books_series_link ON books.id = books_series_link.book")
            joins.append("LEFT JOIN series ON books_series_link.series = series.id")
            conditions.append("series.name LIKE ?")
            params.append(f"%{kwargs['series']}%")
        
        # Titel-Suche
        if 'title' in kwargs:
            conditions.append("books.title LIKE ?")
            params.append(f"%{kwargs['title']}%")
        
        # Query zusammenbauen
        if joins:
            query_parts.extend(joins)
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query = " ".join(query_parts)
        
        with self.connect() as conn:
            cursor = conn.execute(query, params)
            return [{'id': row[0], 'title': row[1]} for row in cursor.fetchall()]
    
    def export_library_info(self):
        """Exportiert Bibliotheks-Informationen"""
        info = {}
        
        with self.connect() as conn:
            # Anzahl Bücher
            cursor = conn.execute("SELECT COUNT(*) FROM books")
            info['total_books'] = cursor.fetchone()[0]
            
            # Anzahl Autoren
            cursor = conn.execute("SELECT COUNT(*) FROM authors")
            info['total_authors'] = cursor.fetchone()[0]
            
            # Verfügbare Formate
            cursor = conn.execute("SELECT DISTINCT format FROM data")
            info['available_formats'] = [row[0] for row in cursor.fetchall()]
            
            # Top Autoren
            cursor = conn.execute("""
                SELECT authors.name, COUNT(*) as book_count
                FROM books_authors_link
                JOIN authors ON books_authors_link.author = authors.id
                GROUP BY authors.name
                ORDER BY book_count DESC
                LIMIT 10
            """)
            info['top_authors'] = [{'name': row[0], 'books': row[1]} for row in cursor.fetchall()]
        
        return info

def demonstrate_database_access():
    """
    Demonstriert direkten Datenbankzugriff
    WARNUNG: Nur für Experten!
    """
    
    # Standard Calibre Library Pfad (macOS)
    default_library = os.path.expanduser("~/Calibre Library")
    
    if not os.path.exists(default_library):
        print("Standard Calibre Library nicht gefunden")
        print("Geben Sie den Pfad zu Ihrer Calibre-Bibliothek ein:")
        library_path = input().strip()
        
        if not library_path or not os.path.exists(library_path):
            print("Ungültiger Pfad")
            return
    else:
        library_path = default_library
    
    try:
        db = CalibreDatabaseController(library_path)
        
        print(f"=== Calibre-Bibliothek: {library_path} ===\n")
        
        # Bibliotheks-Info
        info = db.export_library_info()
        print("Bibliotheks-Übersicht:")
        print(f"  Bücher: {info['total_books']}")
        print(f"  Autoren: {info['total_authors']}")
        print(f"  Formate: {', '.join(info['available_formats'])}")
        
        # Top Autoren
        if info['top_authors']:
            print("\nTop Autoren:")
            for author in info['top_authors'][:5]:
                print(f"  {author['name']}: {author['books']} Buch/Bücher")
        
        # Beispiel: Bücher suchen
        print("\n=== Buch-Suche Beispiele ===")
        
        # Nach Titel suchen
        books = db.search_books_by_metadata(title="Sturmlicht")
        if books:
            print(f"Gefunden {len(books)} Bücher mit 'Sturmlicht' im Titel:")
            for book in books[:3]:
                print(f"  ID {book['id']}: {book['title']}")
                
                # Zeige Formate und Identifier
                formats = db.get_book_formats(book['id'])
                identifiers = db.get_book_identifiers(book['id'])
                
                if formats:
                    print(f"    Formate: {', '.join(f['format'] for f in formats)}")
                if identifiers:
                    print(f"    Identifier: {identifiers}")
        
        print("\n⚠ WARNUNG: Direkter Datenbankzugriff kann die Bibliothek beschädigen!")
        print("Verwenden Sie immer Backups vor Änderungen!")
        
    except Exception as e:
        print(f"Fehler beim Datenbankzugriff: {e}")

if __name__ == "__main__":
    demonstrate_database_access()