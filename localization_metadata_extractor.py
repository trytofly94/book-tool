#!/usr/bin/env python3
"""
Localization Metadata Extractor for Enhanced ASIN Lookup
Extracts titles and language information from books to support multi-language ASIN lookups
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalizationMetadataExtractor:
    """
    Enhanced metadata extractor that focuses on localization information
    for improved ASIN lookup accuracy with non-English books
    """
    
    def __init__(self):
        # Common language code mappings
        self.language_mappings = {
            'de': {'name': 'German', 'amazon_domain': 'amazon.de'},
            'fr': {'name': 'French', 'amazon_domain': 'amazon.fr'},
            'es': {'name': 'Spanish', 'amazon_domain': 'amazon.es'},
            'it': {'name': 'Italian', 'amazon_domain': 'amazon.it'},
            'en': {'name': 'English', 'amazon_domain': 'amazon.com'},
            'deu': {'name': 'German', 'amazon_domain': 'amazon.de'},  # Alternative German code
            'eng': {'name': 'English', 'amazon_domain': 'amazon.com'},  # Alternative English code
        }
        
        # Title pattern analysis for known book series (can be expanded)
        self.title_patterns = {
            'mistborn': {
                'english': ['Mistborn', 'The Final Empire', 'The Well of Ascension', 'The Hero of Ages'],
                'german': ['Kinder des Nebels', 'Krieger des Feuers', 'Herrscher des Lichts'],
            },
            'stormlight': {
                'english': ['The Way of Kings', 'Words of Radiance', 'Oathbringer', 'Rhythm of War'],
                'german': ['Der Weg der Könige', 'Pfad der Winde', 'Schwurträger'],
            },
            'skyward': {
                'english': ['Skyward', 'Starsight', 'Cytonic', 'Defiant'],
                'german': ['Ruf der Sterne', 'Sternensicht'],
            }
        }
    
    def extract_from_epub(self, epub_path: str) -> Dict[str, str]:
        """
        Extract enhanced metadata from EPUB file
        Focus on title and language information for localization
        """
        metadata = {
            'title': '',
            'language': '',
            'author': '',
            'original_title': '',  # For storing alternate titles
            'series': '',
            'series_index': '',
        }
        
        try:
            with zipfile.ZipFile(epub_path, 'r') as epub:
                # Read container.xml to find OPF file
                container_content = epub.read('META-INF/container.xml')
                container_tree = ET.fromstring(container_content)
                
                # Find OPF file path
                ns = {'container': 'urn:oasis:names:tc:opendocument:xmlns:container'}
                opf_path = container_tree.find('.//container:rootfile', ns).get('full-path')
                
                # Read OPF file
                opf_content = epub.read(opf_path)
                opf_tree = ET.fromstring(opf_content)
                
                # Define namespaces
                namespaces = {
                    'dc': 'http://purl.org/dc/elements/1.1/',
                    'opf': 'http://www.idpf.org/2007/opf'
                }
                
                # Extract title
                title_elem = opf_tree.find('.//dc:title', namespaces)
                if title_elem is not None:
                    metadata['title'] = title_elem.text.strip()
                
                # Extract language
                lang_elem = opf_tree.find('.//dc:language', namespaces)
                if lang_elem is not None:
                    metadata['language'] = lang_elem.text.strip()
                
                # Extract author
                creator_elem = opf_tree.find('.//dc:creator', namespaces)
                if creator_elem is not None:
                    metadata['author'] = creator_elem.text.strip()
                
                # Extract series information from meta tags
                for meta_elem in opf_tree.findall('.//meta', namespaces):
                    name = meta_elem.get('name', '').lower()
                    content = meta_elem.get('content', '')
                    
                    if name == 'calibre:series':
                        metadata['series'] = content
                    elif name == 'calibre:series_index':
                        metadata['series_index'] = content
                
                # Try to extract series info from title if not in meta
                if not metadata['series']:
                    series_info = self._extract_series_from_title(metadata['title'])
                    metadata.update(series_info)
                
                logger.info(f"Extracted metadata from {os.path.basename(epub_path)}: "
                           f"Title='{metadata['title']}', Language='{metadata['language']}'")
                
        except Exception as e:
            logger.error(f"Error extracting metadata from {epub_path}: {e}")
        
        return metadata
    
    def extract_from_mobi(self, mobi_path: str) -> Dict[str, str]:
        """
        Extract metadata from MOBI file
        Basic implementation - MOBI parsing is more complex
        """
        metadata = {
            'title': '',
            'language': '',
            'author': '',
            'original_title': '',
            'series': '',
            'series_index': '',
        }
        
        # For now, try to extract from filename as fallback
        filename = os.path.basename(mobi_path)
        metadata.update(self._extract_from_filename(filename))
        
        logger.info(f"Extracted metadata from MOBI {filename} (filename-based)")
        return metadata
    
    def extract_from_filename(self, filepath: str) -> Dict[str, str]:
        """
        Extract metadata from filename as fallback method
        Useful for files where metadata extraction fails
        """
        filename = os.path.basename(filepath)
        return self._extract_from_filename(filename)
    
    def _extract_from_filename(self, filename: str) -> Dict[str, str]:
        """
        Helper method to extract metadata from filename patterns
        """
        metadata = {
            'title': '',
            'language': '',
            'author': '',
            'original_title': '',
            'series': '',
            'series_index': '',
        }
        
        # Remove file extension
        base_name = os.path.splitext(filename)[0]
        
        # Common patterns for Brandon Sanderson books
        patterns = [
            # Pattern: author_series_title.ext
            r'([^_]+)_([^_]+)_(.+)',
            # Pattern: author_title.ext  
            r'([^_]+)_(.+)',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, base_name)
            if match:
                if len(match.groups()) == 3:
                    author, series, title = match.groups()
                    metadata['author'] = author.replace('-', ' ').title()
                    metadata['series'] = series.replace('-', ' ').title()
                    metadata['title'] = title.replace('-', ' ').title()
                elif len(match.groups()) == 2:
                    author, title = match.groups()
                    metadata['author'] = author.replace('-', ' ').title()
                    metadata['title'] = title.replace('-', ' ').title()
                break
        
        # Try to determine language from title patterns
        metadata['language'] = self._guess_language_from_title(metadata['title'])
        
        return metadata
    
    def _extract_series_from_title(self, title: str) -> Dict[str, str]:
        """
        Extract series information from title string
        """
        series_info = {'series': '', 'series_index': ''}
        
        # Common patterns for series information
        patterns = [
            r'^(.+?)\s+(\d+)\s*-\s*(.+)$',  # "Series 01 - Title"
            r'^(.+?)\s+Book\s+(\d+):\s*(.+)$',  # "Series Book 1: Title"
            r'^(.+?)\s+\((\d+)\):\s*(.+)$',  # "Series (1): Title"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, title)
            if match:
                series_info['series'] = match.group(1).strip()
                series_info['series_index'] = match.group(2)
                # Update title to just the book title
                series_info['title'] = match.group(3).strip()
                break
        
        return series_info
    
    def _guess_language_from_title(self, title: str) -> str:
        """
        Guess language from title patterns
        """
        if not title:
            return 'en'  # Default to English
        
        title_lower = title.lower()
        
        # German indicators
        german_indicators = ['kinder des', 'der weg', 'krieger des', 'herrscher des', 'ruf der', 'pfad der']
        if any(indicator in title_lower for indicator in german_indicators):
            return 'de'
        
        # French indicators
        french_indicators = ['le chemin', 'les enfants', 'l\'empire']
        if any(indicator in title_lower for indicator in french_indicators):
            return 'fr'
        
        # Default to English
        return 'en'
    
    def get_localized_search_terms(self, metadata: Dict[str, str]) -> List[Dict[str, str]]:
        """
        Generate search terms optimized for different regions/languages
        Returns list of search term dictionaries with appropriate Amazon domains
        """
        search_terms = []
        
        title = metadata.get('title', '')
        author = metadata.get('author', '')
        language = metadata.get('language', 'en')
        
        # Normalize language code
        lang_code = language.lower()
        if lang_code in ['deu']:
            lang_code = 'de'
        elif lang_code in ['eng']:
            lang_code = 'en'
        
        # Primary search with detected language
        if lang_code in self.language_mappings:
            search_terms.append({
                'title': title,
                'author': author,
                'language': lang_code,
                'amazon_domain': self.language_mappings[lang_code]['amazon_domain'],
                'priority': 1
            })
        
        # Fallback to English if not English already
        if lang_code != 'en':
            # Try to find English equivalent title
            english_title = self._find_english_equivalent(title, author)
            search_terms.append({
                'title': english_title or title,
                'author': author,
                'language': 'en',
                'amazon_domain': 'amazon.com',
                'priority': 2
            })
        
        # Additional search with series name if available
        series = metadata.get('series', '')
        if series:
            search_terms.append({
                'title': f"{series} {author}",
                'author': author,
                'language': lang_code,
                'amazon_domain': self.language_mappings.get(lang_code, {}).get('amazon_domain', 'amazon.com'),
                'priority': 3
            })
        
        return search_terms
    
    def _find_english_equivalent(self, title: str, author: str = '') -> Optional[str]:
        """
        Try to find English equivalent of a localized title
        Uses pattern matching for known book series
        """
        title_lower = title.lower()
        
        for series, translations in self.title_patterns.items():
            # Check if this title matches a known translation
            for lang, titles in translations.items():
                if lang != 'english':
                    for i, translated_title in enumerate(titles):
                        if translated_title.lower() in title_lower or title_lower in translated_title.lower():
                            # Found a match, return corresponding English title
                            english_titles = translations.get('english', [])
                            if i < len(english_titles):
                                return english_titles[i]
        
        return None
    
    def extract_metadata_from_path(self, file_path: str) -> Dict[str, str]:
        """
        Main method to extract metadata from any supported file type
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return {}
        
        file_extension = Path(file_path).suffix.lower()
        
        try:
            if file_extension == '.epub':
                return self.extract_from_epub(file_path)
            elif file_extension in ['.mobi', '.azw', '.azw3']:
                return self.extract_from_mobi(file_path)
            else:
                logger.warning(f"Unsupported file type: {file_extension}. Using filename extraction.")
                return self.extract_from_filename(file_path)
        except Exception as e:
            logger.error(f"Error extracting metadata from {file_path}: {e}")
            # Fallback to filename extraction
            return self.extract_from_filename(file_path)

def test_localization_extractor():
    """Test the localization metadata extractor with sample files"""
    extractor = LocalizationMetadataExtractor()
    
    # Test file path
    test_file = '/Volumes/SSD-MacMini/Temp/Calibre-Ingest/book-pipeline/sanderson_mistborn1_kinder-des-nebels.epub'
    
    if os.path.exists(test_file):
        print("=== Testing Localization Metadata Extractor ===")
        metadata = extractor.extract_metadata_from_path(test_file)
        
        print(f"File: {os.path.basename(test_file)}")
        print(f"Title: {metadata.get('title')}")
        print(f"Language: {metadata.get('language')}")
        print(f"Author: {metadata.get('author')}")
        print(f"Series: {metadata.get('series')}")
        
        print("\n=== Generated Search Terms ===")
        search_terms = extractor.get_localized_search_terms(metadata)
        for i, term in enumerate(search_terms, 1):
            print(f"{i}. {term['title']} by {term['author']} "
                  f"({term['language']}) -> {term['amazon_domain']}")
    
    else:
        print(f"Test file not found: {test_file}")
        print("Testing with filename extraction...")
        
        test_filename = "sanderson_mistborn1_kinder-des-nebels.epub"
        metadata = extractor.extract_from_filename(test_filename)
        
        print(f"Filename: {test_filename}")
        print(f"Extracted: {metadata}")

if __name__ == "__main__":
    test_localization_extractor()