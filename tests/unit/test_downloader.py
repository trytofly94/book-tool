"""
Unit tests for BookDownloader functionality.
"""

import pytest
import tempfile
import json
import subprocess
import os
from pathlib import Path
from unittest.mock import patch, mock_open, Mock, MagicMock, call
from concurrent.futures import ThreadPoolExecutor

from calibre_books.core.downloader import (
    BookDownloader, 
    DownloadResult, 
    BookRequest
)
from calibre_books.core.exceptions import (
    ValidationError, FormatError, LibrarianError, NetworkError, ConfigurationError
)


class TestDownloadResult:
    """Test DownloadResult dataclass."""
    
    def test_download_result_creation(self):
        """Test DownloadResult creation."""
        result = DownloadResult(
            title="Test Book",
            author="Test Author", 
            filepath=Path("/test/path.epub"),
            success=True,
            format="epub",
            file_size=1024
        )
        
        assert result.title == "Test Book"
        assert result.author == "Test Author"
        assert result.filepath == Path("/test/path.epub")
        assert result.success is True
        assert result.format == "epub"
        assert result.file_size == 1024
        assert result.error is None
    
    def test_download_result_with_error(self):
        """Test DownloadResult with error."""
        result = DownloadResult(
            title="Failed Book",
            author="Unknown",
            filepath=None,
            success=False,
            error="Download failed"
        )
        
        assert result.success is False
        assert result.error == "Download failed"
        assert result.filepath is None


class TestBookRequest:
    """Test BookRequest dataclass."""
    
    def test_book_request_minimal(self):
        """Test BookRequest with minimal data."""
        book = BookRequest(title="Test Book")
        
        assert book.title == "Test Book"
        assert book.author is None
        assert book.series is None
        assert book.format == "mobi"
    
    def test_book_request_complete(self):
        """Test BookRequest with complete data."""
        book = BookRequest(
            title="Test Book",
            author="Test Author",
            series="Test Series",
            format="epub"
        )
        
        assert book.title == "Test Book"
        assert book.author == "Test Author"
        assert book.series == "Test Series"
        assert book.format == "epub"


class TestBookDownloader:
    """Test BookDownloader functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def config(self, temp_dir):
        """Create test configuration."""
        return {
            'default_format': 'mobi',
            'download_path': str(temp_dir / 'downloads'),
            'librarian_path': 'librarian',
            'max_parallel': 2,
            'quality': 'high',
            'search_timeout': 60,
            'download_timeout': 300
        }
    
    @pytest.fixture
    def downloader(self, config):
        """Create BookDownloader instance."""
        with patch.object(BookDownloader, '_validate_configuration'):
            return BookDownloader(config)
    
    def test_downloader_initialization(self, config, temp_dir):
        """Test BookDownloader initialization."""
        downloader = BookDownloader(config)
        
        assert downloader.default_format == 'mobi'
        assert downloader.download_path == Path(temp_dir / 'downloads')
        assert downloader.librarian_path == 'librarian'
        assert downloader.max_parallel == 2
        assert downloader.quality == 'high'
        
        # Check that download directory was created
        assert downloader.download_path.exists()
    
    def test_downloader_default_config(self):
        """Test BookDownloader with minimal config."""
        config = {}
        downloader = BookDownloader(config)
        
        assert downloader.default_format == 'mobi'
        assert downloader.librarian_path == 'librarian'
        assert downloader.max_parallel == 1
        assert downloader.quality == 'high'
    
    @patch('subprocess.run')
    def test_check_librarian_available(self, mock_run, downloader):
        """Test librarian availability check when available."""
        mock_run.return_value = Mock(returncode=0)
        
        requirements = downloader.check_system_requirements()
        
        assert requirements['librarian'] is True
        mock_run.assert_called_once_with(
            ['librarian', '--help'],
            capture_output=True, 
            text=True, 
            timeout=10
        )
    
    @patch('subprocess.run')
    def test_check_librarian_unavailable(self, mock_run, downloader):
        """Test librarian availability check when unavailable."""
        mock_run.side_effect = FileNotFoundError()
        
        requirements = downloader.check_system_requirements()
        
        assert requirements['librarian'] is False
    
    @patch('subprocess.run')
    def test_check_librarian_timeout(self, mock_run, downloader):
        """Test librarian availability check with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired('librarian', 10)
        
        requirements = downloader.check_system_requirements()
        
        assert requirements['librarian'] is False
    
    def test_download_books_no_criteria(self, downloader):
        """Test download_books with no search criteria."""
        with pytest.raises(ValueError, match="Must specify at least one of"):
            downloader.download_books()
    
    @patch.object(BookDownloader, '_search_books')
    def test_download_books_no_results(self, mock_search, downloader, temp_dir):
        """Test download_books with no search results."""
        mock_search.return_value = []
        
        results = downloader.download_books(title="Nonexistent Book")
        
        assert results == []
        mock_search.assert_called_once()
    
    @patch.object(BookDownloader, '_search_books')
    @patch.object(BookDownloader, '_download_single_book')
    def test_download_books_success(self, mock_download, mock_search, downloader):
        """Test successful download_books operation."""
        # Mock search results
        mock_search.return_value = [
            {
                'title': 'Test Book 1',
                'author': 'Author 1',
                'format': 'mobi',
                'hash': 'hash1'
            },
            {
                'title': 'Test Book 2',
                'author': 'Author 2',
                'format': 'mobi',
                'hash': 'hash2'
            }
        ]
        
        # Mock download results
        mock_download.side_effect = [
            DownloadResult("Test Book 1", "Author 1", Path("/test1.mobi"), True),
            DownloadResult("Test Book 2", "Author 2", Path("/test2.mobi"), True)
        ]
        
        results = downloader.download_books(author="Test Author", format="mobi")
        
        assert len(results) == 2
        assert all(r.success for r in results)
        assert mock_download.call_count == 2
    
    @patch.object(BookDownloader, '_search_books')
    def test_download_books_format_filter(self, mock_search, downloader):
        """Test download_books filters by format correctly."""
        mock_search.return_value = [
            {
                'title': 'Test Book 1',
                'author': 'Author 1',
                'format': 'epub',  # Different format
                'hash': 'hash1'
            },
            {
                'title': 'Test Book 2',
                'author': 'Author 2',
                'format': 'mobi',  # Correct format
                'hash': 'hash2'
            }
        ]
        
        with patch.object(downloader, '_download_single_book') as mock_download:
            mock_download.return_value = DownloadResult("Test Book 2", "Author 2", Path("/test2.mobi"), True)
            
            results = downloader.download_books(author="Test Author", format="mobi")
            
            assert len(results) == 1
            assert results[0].title == "Test Book 2"
    
    def test_download_books_progress_callback(self, downloader):
        """Test download_books with progress callback."""
        progress_calls = []
        def progress_callback(current, total):
            progress_calls.append((current, total))
        
        with patch.object(downloader, '_search_books') as mock_search:
            with patch.object(downloader, '_download_single_book') as mock_download:
                mock_search.return_value = [
                    {'title': 'Book 1', 'author': 'Author', 'format': 'mobi', 'hash': 'hash1'}
                ]
                mock_download.return_value = DownloadResult("Book 1", "Author", Path("/book1.mobi"), True)
                
                downloader.download_books(
                    title="Test",
                    progress_callback=progress_callback
                )
                
                # Should have progress calls: (0, 1) and (1, 1)
                assert len(progress_calls) >= 2
                assert progress_calls[-1] == (1, 1)  # Final call
    
    def test_download_batch_empty_list(self, downloader):
        """Test download_batch with empty book list."""
        results = downloader.download_batch([])
        assert results == []
    
    @patch.object(BookDownloader, '_download_book_request')
    def test_download_batch_sequential(self, mock_download, downloader):
        """Test download_batch in sequential mode."""
        books = [
            BookRequest(title="Book 1", author="Author 1"),
            BookRequest(title="Book 2", author="Author 2")
        ]
        
        mock_download.side_effect = [
            DownloadResult("Book 1", "Author 1", Path("/book1.mobi"), True),
            DownloadResult("Book 2", "Author 2", Path("/book2.mobi"), True)
        ]
        
        results = downloader.download_batch(books, parallel=1)
        
        assert len(results) == 2
        assert all(r.success for r in results)
        assert mock_download.call_count == 2
    
    @patch.object(BookDownloader, '_download_book_request')
    def test_download_batch_parallel(self, mock_download, downloader):
        """Test download_batch in parallel mode."""
        books = [
            BookRequest(title="Book 1", author="Author 1"),
            BookRequest(title="Book 2", author="Author 2")
        ]
        
        mock_download.side_effect = [
            DownloadResult("Book 1", "Author 1", Path("/book1.mobi"), True),
            DownloadResult("Book 2", "Author 2", Path("/book2.mobi"), True)
        ]
        
        results = downloader.download_batch(books, parallel=2)
        
        assert len(results) == 2
        assert mock_download.call_count == 2
    
    @patch.object(BookDownloader, '_download_book_request')
    def test_download_batch_with_exception(self, mock_download, downloader):
        """Test download_batch handles exceptions properly."""
        books = [
            BookRequest(title="Book 1", author="Author 1"),
            BookRequest(title="Book 2", author="Author 2")
        ]
        
        # First download succeeds, second raises exception
        mock_download.side_effect = [
            DownloadResult("Book 1", "Author 1", Path("/book1.mobi"), True),
            Exception("Download failed")
        ]
        
        results = downloader.download_batch(books, parallel=2)
        
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert "Download failed" in results[1].error
    
    @patch('subprocess.run')
    def test_download_from_url_wget_success(self, mock_run, downloader, temp_dir):
        """Test successful URL download with wget."""
        url = "https://example.com/book.epub"
        
        # Mock successful wget
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        # Create actual file for test to avoid complex mocking
        output_path = downloader.download_path / "book.epub"
        output_path.write_text("test content")
        
        result = downloader.download_from_url(url)
        
        assert result.success is True
        assert result.title == "book.epub"
        assert result.file_size > 0
        assert result.error is None
    
    @patch('subprocess.run')
    def test_download_from_url_wget_fail_curl_success(self, mock_run, downloader):
        """Test URL download where wget fails but curl succeeds."""
        url = "https://example.com/book.epub"
        
        # First call (wget) fails, second call (curl) succeeds
        mock_run.side_effect = [
            Mock(returncode=1, stderr="wget failed"),  # wget fails
            Mock(returncode=0, stderr="")              # curl succeeds
        ]
        
        # Create actual file for test
        output_path = downloader.download_path / "book.epub"
        output_path.write_text("test content")
        
        result = downloader.download_from_url(url)
        
        assert result.success is True
        assert mock_run.call_count == 2
    
    @patch('subprocess.run')
    def test_download_from_url_timeout(self, mock_run, downloader):
        """Test URL download with timeout."""
        url = "https://example.com/book.epub"
        
        mock_run.side_effect = subprocess.TimeoutExpired("wget", 300)
        
        result = downloader.download_from_url(url)
        
        assert result.success is False
        assert "timed out" in result.error.lower()
    
    @patch('subprocess.run')
    def test_download_from_url_both_fail(self, mock_run, downloader):
        """Test URL download where both wget and curl fail."""
        url = "https://example.com/book.epub"
        
        # Both wget and curl fail
        mock_run.side_effect = [
            Mock(returncode=1, stderr="wget failed"),
            Mock(returncode=1, stderr="curl failed")
        ]
        
        result = downloader.download_from_url(url)
        
        assert result.success is False
        assert "curl failed" in result.error
    
    @patch('subprocess.run')
    def test_download_from_url_empty_file(self, mock_run, downloader):
        """Test URL download produces empty file."""
        url = "https://example.com/book.epub"
        
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        # Create empty file for test
        output_path = downloader.download_path / "book.epub"
        output_path.touch()  # Create empty file
        
        result = downloader.download_from_url(url)
        
        assert result.success is False
        assert "empty" in result.error.lower()
    
    @patch('subprocess.run')
    def test_download_from_url_custom_filename(self, mock_run, downloader):
        """Test URL download with custom filename."""
        url = "https://example.com/book.epub"
        custom_filename = "my_book.epub"
        
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        # Create actual file for test
        output_path = downloader.download_path / custom_filename
        output_path.write_text("test content")
        
        result = downloader.download_from_url(url, filename=custom_filename)
        
        assert result.success is True
        assert result.title == custom_filename
    
    def test_parse_book_list_nonexistent_file(self, downloader):
        """Test parsing nonexistent book list file."""
        with pytest.raises(ValidationError, match="Book list file not found"):
            downloader.parse_book_list(Path("/nonexistent/file.txt"))
    
    def test_parse_book_list_valid_file(self, downloader, temp_dir):
        """Test parsing valid book list file."""
        book_list_content = """# Comment line
Book Title 1
Book Title 2|Author Name
Book Title 3|Author Name|Series Name

# Another comment
Book Title 4|Another Author|Another Series|Extra Field"""
        
        book_list_file = temp_dir / "books.txt"
        book_list_file.write_text(book_list_content)
        
        books = downloader.parse_book_list(book_list_file)
        
        assert len(books) == 4
        
        # Check first book (title only)
        assert books[0].title == "Book Title 1"
        assert books[0].author is None
        assert books[0].series is None
        
        # Check second book (title and author)
        assert books[1].title == "Book Title 2"
        assert books[1].author == "Author Name"
        assert books[1].series is None
        
        # Check third book (title, author, and series)
        assert books[2].title == "Book Title 3"
        assert books[2].author == "Author Name"
        assert books[2].series == "Series Name"
        
        # Check fourth book (with extra fields)
        assert books[3].title == "Book Title 4"
        assert books[3].author == "Another Author"
        assert books[3].series == "Another Series"
    
    def test_parse_book_list_empty_file(self, downloader, temp_dir):
        """Test parsing empty book list file."""
        book_list_file = temp_dir / "empty.txt"
        book_list_file.write_text("")
        
        with pytest.raises(FormatError, match="No valid book entries found"):
            downloader.parse_book_list(book_list_file)
    
    def test_parse_book_list_comments_only(self, downloader, temp_dir):
        """Test parsing file with only comments."""
        book_list_content = """# This is a comment
# Another comment

# Yet another comment"""
        
        book_list_file = temp_dir / "comments.txt"
        book_list_file.write_text(book_list_content)
        
        with pytest.raises(FormatError, match="No valid book entries found"):
            downloader.parse_book_list(book_list_file)
    
    def test_parse_book_list_invalid_extension(self, downloader, temp_dir):
        """Test parsing file with invalid extension."""
        book_list_file = temp_dir / "books.json"
        book_list_file.write_text("Some content")
        
        with pytest.raises(ValidationError, match="Unsupported file format"):
            downloader.parse_book_list(book_list_file)
    
    @patch('subprocess.run')
    def test_search_books_success(self, mock_run, downloader, temp_dir):
        """Test successful book search."""
        search_results = [
            {
                'title': 'Test Book',
                'author': 'Test Author',
                'format': 'mobi',
                'hash': 'testhash'
            }
        ]
        
        # Mock subprocess call
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Create mock results file
        results_file = downloader.download_path / 'search_results.json'
        results_file.parent.mkdir(parents=True, exist_ok=True)
        results_file.write_text(json.dumps(search_results))
        
        results = downloader._search_books("test query", downloader.download_path)
        
        assert len(results) == 1
        assert results[0]['title'] == 'Test Book'
    
    @patch('subprocess.run')
    def test_search_books_command_failed(self, mock_run, downloader):
        """Test search books when command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'librarian')
        
        results = downloader._search_books("test query", downloader.download_path)
        
        assert results == []
    
    @patch('subprocess.run')
    def test_search_books_timeout(self, mock_run, downloader):
        """Test search books with timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired('librarian', 60)
        
        results = downloader._search_books("test query", downloader.download_path)
        
        assert results == []
    
    @patch('subprocess.run')
    def test_search_books_invalid_json(self, mock_run, downloader, temp_dir):
        """Test search books with invalid JSON results."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Create invalid JSON file
        results_file = downloader.download_path / 'search_results.json'
        results_file.parent.mkdir(parents=True, exist_ok=True)
        results_file.write_text("invalid json")
        
        results = downloader._search_books("test query", downloader.download_path)
        
        assert results == []
    
    def test_create_safe_filename(self, downloader):
        """Test safe filename creation."""
        # Test normal title
        filename = downloader._create_safe_filename("Normal Title", "epub")
        assert filename == "Normal_Title.epub"
        
        # Test title with special characters
        filename = downloader._create_safe_filename("Title: With/Special\\Characters!", "mobi")
        assert filename == "Title_WithSpecialCharacters.mobi"
        
        # Test very long title
        long_title = "A" * 150
        filename = downloader._create_safe_filename(long_title, "pdf")
        assert len(filename) <= 104  # 100 chars + ".pdf"
        assert filename.endswith(".pdf")
    
    @patch('subprocess.run')
    def test_download_single_book_success(self, mock_run, downloader, temp_dir):
        """Test successful single book download."""
        book_data = {
            'title': 'Test Book',
            'author': 'Test Author',
            'hash': 'testhash'
        }
        
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Mock file operations
        target_path = downloader.download_path / "Test_Book.mobi"
        with patch('pathlib.Path.exists') as mock_exists:
            with patch('pathlib.Path.stat') as mock_stat:
                with patch('pathlib.Path.rename') as mock_rename:
                    # File exists in target location
                    mock_exists.return_value = True
                    mock_stat.return_value = Mock(st_size=1024)
                    
                    result = downloader._download_single_book(book_data, downloader.download_path, "mobi")
                    
                    assert result.success is True
                    assert result.title == "Test Book"
                    assert result.author == "Test Author"
                    assert result.file_size == 1024
    
    @patch('subprocess.run')
    def test_download_single_book_no_hash(self, mock_run, downloader):
        """Test single book download with no hash."""
        book_data = {
            'title': 'Test Book',
            'author': 'Test Author'
            # No hash
        }
        
        result = downloader._download_single_book(book_data, downloader.download_path, "mobi")
        
        assert result.success is False
        assert "No hash ID found" in result.error
    
    @patch('subprocess.run')
    def test_download_single_book_command_failed(self, mock_run, downloader):
        """Test single book download when command fails."""
        book_data = {
            'title': 'Test Book',
            'author': 'Test Author',
            'hash': 'testhash'
        }
        
        mock_run.return_value = Mock(returncode=1, stderr="Download failed")
        
        result = downloader._download_single_book(book_data, downloader.download_path, "mobi")
        
        assert result.success is False
        assert "Download failed" in result.error
    
    @patch('subprocess.run')
    def test_download_single_book_timeout(self, mock_run, downloader):
        """Test single book download with timeout."""
        book_data = {
            'title': 'Test Book',
            'author': 'Test Author',
            'hash': 'testhash'
        }
        
        mock_run.side_effect = subprocess.TimeoutExpired('librarian', 300)
        
        result = downloader._download_single_book(book_data, downloader.download_path, "mobi")
        
        assert result.success is False
        assert "timed out" in result.error.lower()