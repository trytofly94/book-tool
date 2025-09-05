
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
