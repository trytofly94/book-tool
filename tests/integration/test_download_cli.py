"""
Integration tests for download CLI commands.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from click.testing import CliRunner

from calibre_books.cli.download import download, books, batch, url
from calibre_books.core.downloader import BookDownloader, DownloadResult, BookRequest
from calibre_books.config.manager import ConfigManager


class TestDownloadCliCommands:
    """Test download CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.test_config = {
            'default_format': 'mobi',
            'download_path': '~/Downloads/Books',
            'librarian_path': 'librarian',
            'max_parallel': 2,
            'quality': 'high',
            'search_timeout': 60,
            'download_timeout': 300
        }
    
    def create_mock_context(self):
        """Create a mock Click context with test configuration."""
        mock_config_manager = Mock()
        mock_config_manager.get_download_config.return_value = self.test_config
        
        return {
            'config': mock_config_manager,
            'dry_run': False
        }
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_books_command_success(self, mock_progress, mock_downloader_class):
        """Test successful books download command."""
        # Mock downloader and results
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        
        mock_results = [
            DownloadResult("Book 1", "Author 1", Path("/books/book1.mobi"), True),
            DownloadResult("Book 2", "Author 2", Path("/books/book2.mobi"), True)
        ]
        mock_downloader.download_books.return_value = mock_results
        
        # Mock progress manager
        mock_progress_ctx = Mock()
        mock_progress_ctx.update = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        # Run command
        result = self.runner.invoke(
            books, 
            ['--author', 'Test Author', '--format', 'mobi'],
            obj=self.create_mock_context()
        )
        
        assert result.exit_code == 0
        assert "Successfully downloaded 2 books" in result.output
        assert "Book 1 by Author 1" in result.output
        assert "Book 2 by Author 2" in result.output
        
        # Verify downloader was called correctly
        mock_downloader.download_books.assert_called_once_with(
            series=None,
            author='Test Author',
            title=None,
            format='mobi',
            output_dir=None,
            max_results=10,
            quality='high',
            progress_callback=mock_progress_ctx.update
        )
    
    @patch('calibre_books.cli.download.BookDownloader')
    def test_books_command_no_criteria(self, mock_downloader_class):
        """Test books command with no search criteria."""
        result = self.runner.invoke(
            books,
            [],
            obj=self.create_mock_context()
        )
        
        assert result.exit_code == 1
        assert "Must specify at least one of --series, --author, or --title" in result.output
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_books_command_no_results(self, mock_progress, mock_downloader_class):
        """Test books command with no results found."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.download_books.return_value = []
        
        mock_progress_ctx = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        result = self.runner.invoke(
            books,
            ['--title', 'Nonexistent Book'],
            obj=self.create_mock_context()
        )
        
        assert result.exit_code == 0
        assert "No books found matching criteria" in result.output
    
    @patch('calibre_books.cli.download.BookDownloader')
    def test_books_command_dry_run(self, mock_downloader_class):
        """Test books command in dry run mode."""
        mock_context = self.create_mock_context()
        mock_context['dry_run'] = True
        
        result = self.runner.invoke(
            books,
            ['--series', 'Test Series', '--format', 'epub'],
            obj=mock_context
        )
        
        assert result.exit_code == 0
        assert "DRY RUN: Would download books with criteria:" in result.output
        assert "Series: Test Series" in result.output
        assert "Format: epub" in result.output
        
        # Downloader is created but not used in dry run
        mock_downloader_class.assert_called_once()
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_books_command_with_all_options(self, mock_progress, mock_downloader_class):
        """Test books command with all options specified."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.download_books.return_value = [
            DownloadResult("Book 1", "Author 1", Path("/custom/book1.epub"), True)
        ]
        
        mock_progress_ctx = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        with self.runner.isolated_filesystem():
            Path("custom_output").mkdir()
            
            result = self.runner.invoke(
                books,
                [
                    '--series', 'Test Series',
                    '--author', 'Test Author', 
                    '--title', 'Test Book',
                    '--format', 'epub',
                    '--output-dir', 'custom_output',
                    '--max-results', '5',
                    '--quality', 'medium'
                ],
                obj=self.create_mock_context()
            )
        
        assert result.exit_code == 0
        
        mock_downloader.download_books.assert_called_once_with(
            series='Test Series',
            author='Test Author',
            title='Test Book',
            format='epub',
            output_dir=Path('custom_output'),
            max_results=5,
            quality='medium',
            progress_callback=mock_progress_ctx.update
        )
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_books_command_exception_handling(self, mock_progress, mock_downloader_class):
        """Test books command exception handling."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.download_books.side_effect = Exception("Network error")
        
        mock_progress_ctx = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        result = self.runner.invoke(
            books,
            ['--title', 'Test Book'],
            obj=self.create_mock_context()
        )
        
        assert result.exit_code == 1
        assert "Download failed: Network error" in result.output
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_batch_command_success(self, mock_progress, mock_downloader_class):
        """Test successful batch download command."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        
        # Mock parse_book_list
        mock_books = [
            BookRequest(title="Book 1", author="Author 1"),
            BookRequest(title="Book 2", author="Author 2")
        ]
        mock_downloader.parse_book_list.return_value = mock_books
        
        # Mock download_batch
        mock_results = [
            DownloadResult("Book 1", "Author 1", Path("/books/book1.mobi"), True),
            DownloadResult("Book 2", "Author 2", Path("/books/book2.mobi"), False, error="Download failed")
        ]
        mock_downloader.download_batch.return_value = mock_results
        
        mock_progress_ctx = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        with self.runner.isolated_filesystem():
            # Create test input file
            Path("books_list.txt").write_text("Book 1|Author 1\nBook 2|Author 2")
            
            result = self.runner.invoke(
                batch,
                ['--input-file', 'books_list.txt', '--parallel', '3'],
                obj=self.create_mock_context()
            )
        
        assert result.exit_code == 0
        assert "Batch download completed" in result.output
        assert "Successful: 1" in result.output
        assert "Failed: 1" in result.output
        
        mock_downloader.parse_book_list.assert_called_once_with(Path('books_list.txt'))
        mock_downloader.download_batch.assert_called_once_with(
            mock_books,
            format='mobi',
            output_dir=None,
            parallel=3,
            progress_callback=mock_progress_ctx.update
        )
    
    @patch('calibre_books.cli.download.BookDownloader')
    def test_batch_command_dry_run(self, mock_downloader_class):
        """Test batch command in dry run mode."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        
        mock_books = [
            BookRequest(title="Book 1", author="Author 1"),
            BookRequest(title="Book 2", author="Author 2"),
            BookRequest(title="Book 3", author="Author 3"),
            BookRequest(title="Book 4", author="Author 4"),
            BookRequest(title="Book 5", author="Author 5"),
            BookRequest(title="Book 6", author="Author 6")  # More than 5 for truncation test
        ]
        mock_downloader.parse_book_list.return_value = mock_books
        
        mock_context = self.create_mock_context()
        mock_context['dry_run'] = True
        
        with self.runner.isolated_filesystem():
            Path("books_list.txt").write_text("books content")
            
            result = self.runner.invoke(
                batch,
                ['--input-file', 'books_list.txt'],
                obj=mock_context
            )
        
        assert result.exit_code == 0
        assert "DRY RUN: Would download 6 books:" in result.output
        assert "Book 1 by Author 1" in result.output
        assert "... and 1 more" in result.output
        
        mock_downloader.download_batch.assert_not_called()
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_batch_command_exception_handling(self, mock_progress, mock_downloader_class):
        """Test batch command exception handling."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.parse_book_list.side_effect = FileNotFoundError("File not found")
        
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                batch,
                ['--input-file', 'nonexistent.txt'],
                obj=self.create_mock_context()
            )
        
        # Click exits with code 2 for usage errors, code 1 for application errors
        assert result.exit_code == 2
        assert "No such file or directory" in result.output or "Error:" in result.output
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_url_command_success(self, mock_progress, mock_downloader_class):
        """Test successful URL download command."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        
        mock_result = DownloadResult(
            "book.epub", 
            "Unknown", 
            Path("/downloads/book.epub"), 
            True,
            file_size=1024
        )
        mock_downloader.download_from_url.return_value = mock_result
        
        mock_progress_ctx = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        result = self.runner.invoke(
            url,
            ['--url', 'https://example.com/book.epub'],
            obj=self.create_mock_context()
        )
        
        assert result.exit_code == 0
        assert "Successfully downloaded: /downloads/book.epub" in result.output
        
        mock_downloader.download_from_url.assert_called_once_with(
            'https://example.com/book.epub',
            output_dir=None,
            filename=None,
            progress_callback=mock_progress_ctx.update
        )
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_url_command_failure(self, mock_progress, mock_downloader_class):
        """Test URL download command failure."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        
        mock_result = DownloadResult(
            "book.epub", 
            "Unknown", 
            None, 
            False,
            error="Download timed out"
        )
        mock_downloader.download_from_url.return_value = mock_result
        
        mock_progress_ctx = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        result = self.runner.invoke(
            url,
            ['--url', 'https://example.com/book.epub'],
            obj=self.create_mock_context()
        )
        
        assert result.exit_code == 1
        assert "Download failed: Download timed out" in result.output
    
    @patch('calibre_books.cli.download.BookDownloader')
    def test_url_command_dry_run(self, mock_downloader_class):
        """Test URL download command in dry run mode."""
        mock_context = self.create_mock_context()
        mock_context['dry_run'] = True
        
        result = self.runner.invoke(
            url,
            [
                '--url', 'https://example.com/book.epub',
                '--filename', 'custom_book.epub'
            ],
            obj=mock_context
        )
        
        assert result.exit_code == 0
        assert "DRY RUN: Would download from URL: https://example.com/book.epub" in result.output
        assert "Filename: custom_book.epub" in result.output
        
        # Downloader is created but not used in dry run
        mock_downloader_class.assert_called_once()
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_url_command_with_custom_options(self, mock_progress, mock_downloader_class):
        """Test URL download command with custom options."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        
        mock_result = DownloadResult(
            "custom_book.epub", 
            "Unknown", 
            Path("/custom/custom_book.epub"), 
            True
        )
        mock_downloader.download_from_url.return_value = mock_result
        
        mock_progress_ctx = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        with self.runner.isolated_filesystem():
            Path("custom_dir").mkdir()
            
            result = self.runner.invoke(
                url,
                [
                    '--url', 'https://example.com/book.epub',
                    '--output-dir', 'custom_dir',
                    '--filename', 'custom_book.epub'
                ],
                obj=self.create_mock_context()
            )
        
        assert result.exit_code == 0
        
        mock_downloader.download_from_url.assert_called_once_with(
            'https://example.com/book.epub',
            output_dir=Path('custom_dir'),
            filename='custom_book.epub',
            progress_callback=mock_progress_ctx.update
        )
    
    @patch('calibre_books.cli.download.BookDownloader')
    @patch('calibre_books.cli.download.ProgressManager')
    def test_url_command_exception_handling(self, mock_progress, mock_downloader_class):
        """Test URL command exception handling."""
        mock_downloader = Mock()
        mock_downloader_class.return_value = mock_downloader
        mock_downloader.download_from_url.side_effect = Exception("Network error")
        
        mock_progress_ctx = Mock()
        mock_progress.return_value.__enter__.return_value = mock_progress_ctx
        
        result = self.runner.invoke(
            url,
            ['--url', 'https://example.com/book.epub'],
            obj=self.create_mock_context()
        )
        
        assert result.exit_code == 1
        assert "URL download failed: Network error" in result.output
    
    def test_download_group_help(self):
        """Test download group help message."""
        result = self.runner.invoke(download, ['--help'])
        
        assert result.exit_code == 0
        assert "Download books from various sources." in result.output
        assert "books" in result.output
        assert "batch" in result.output
        assert "url" in result.output
    
    def test_books_command_help(self):
        """Test books command help message."""
        result = self.runner.invoke(books, ['--help'])
        
        assert result.exit_code == 0
        assert "Download books based on search criteria." in result.output
        assert "--series" in result.output
        assert "--author" in result.output
        assert "--title" in result.output
        assert "--format" in result.output
    
    def test_batch_command_help(self):
        """Test batch command help message."""
        result = self.runner.invoke(batch, ['--help'])
        
        assert result.exit_code == 0
        assert "Download multiple books from a list file." in result.output
        assert "--input-file" in result.output
        assert "--parallel" in result.output
    
    def test_url_command_help(self):
        """Test URL command help message."""
        result = self.runner.invoke(url, ['--help'])
        
        assert result.exit_code == 0
        assert "Download book from direct URL." in result.output
        assert "--url" in result.output
        assert "--output-dir" in result.output
        assert "--filename" in result.output