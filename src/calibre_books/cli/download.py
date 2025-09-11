"""
Download command module for Calibre Books CLI.

This module provides commands for downloading books using various sources
and integrating with the librarian CLI tool.
"""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from calibre_books.core.downloader import BookDownloader
from calibre_books.utils.progress import ProgressManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def download(ctx: click.Context) -> None:
    """Download books from various sources."""


@download.command()
@click.option(
    "--series",
    "-s",
    help="Download all books in a series.",
)
@click.option(
    "--author",
    "-a",
    help="Download books by specific author.",
)
@click.option(
    "--title",
    "-t",
    help="Download specific book by title.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["mobi", "epub", "pdf", "azw3"]),
    default="mobi",
    help="Preferred download format.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for downloaded books.",
)
@click.option(
    "--max-results",
    "-m",
    type=int,
    default=10,
    help="Maximum number of books to download.",
)
@click.option(
    "--quality",
    type=click.Choice(["high", "medium", "low"]),
    default="high",
    help="Download quality preference.",
)
@click.pass_context
def books(
    ctx: click.Context,
    series: Optional[str],
    author: Optional[str],
    title: Optional[str],
    format: str,
    output_dir: Optional[Path],
    max_results: int,
    quality: str,
) -> None:
    """
    Download books based on search criteria.

    Examples:
        book-tool download books --series "Stormlight Archive"
        book-tool download books --author "Brandon Sanderson" --format epub
        book-tool download books --title "The Way of Kings"
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    if not any([series, author, title]):
        console.print(
            "[red]Error: Must specify at least one of --series, --author, or --title[/red]"
        )
        ctx.exit(1)

    try:
        downloader = BookDownloader(config.get_download_config())

        if dry_run:
            console.print(
                "[yellow]DRY RUN: Would download books with criteria:[/yellow]"
            )
            if series:
                console.print(f"  Series: {series}")
            if author:
                console.print(f"  Author: {author}")
            if title:
                console.print(f"  Title: {title}")
            console.print(f"  Format: {format}")
            console.print(f"  Max results: {max_results}")
            console.print(f"  Quality: {quality}")
            return

        # Create progress manager for long-running operation
        with ProgressManager("Downloading books") as progress:
            results = downloader.download_books(
                series=series,
                author=author,
                title=title,
                format=format,
                output_dir=output_dir,
                max_results=max_results,
                quality=quality,
                progress_callback=progress.update,
            )

        if results:
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]

            if successful:
                console.print(
                    f"[green]Successfully downloaded {len(successful)} books[/green]"
                )
                for result in successful:
                    console.print(f"  • {result.title} by {result.author}")

            if failed:
                console.print(
                    f"[yellow]Failed to download {len(failed)} books[/yellow]"
                )
                for result in failed:
                    console.print(
                        f"  • {result.title} by {result.author}: {result.error}"
                    )
        else:
            console.print("[yellow]No books found matching criteria[/yellow]")

    except Exception as e:
        logger.error(f"Download failed: {e}")
        console.print(f"[red]Download failed: {e}[/red]")
        ctx.exit(1)


@download.command()
@click.option(
    "--input-file",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="File containing list of books to download.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["mobi", "epub", "pdf", "azw3"]),
    default="mobi",
    help="Preferred download format.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for downloaded books.",
)
@click.option(
    "--parallel",
    "-p",
    type=int,
    default=1,
    help="Number of parallel downloads.",
)
@click.pass_context
def batch(
    ctx: click.Context,
    input_file: Path,
    format: str,
    output_dir: Optional[Path],
    parallel: int,
) -> None:
    """
    Download multiple books from a list file.

    The input file should contain one book per line in the format:
    Title|Author or just Title

    Examples:
        book-tool download batch -i books_list.txt --parallel 3
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        downloader = BookDownloader(config.get_download_config())

        # Read book list from file
        books_to_download = downloader.parse_book_list(input_file)

        if dry_run:
            console.print(
                f"[yellow]DRY RUN: Would download {len(books_to_download)} books:[/yellow]"
            )
            for book in books_to_download[:5]:  # Show first 5
                console.print(f"  • {book.title} by {book.author}")
            if len(books_to_download) > 5:
                console.print(f"  ... and {len(books_to_download) - 5} more")
            return

        # Start batch download with progress tracking
        with ProgressManager(f"Downloading {len(books_to_download)} books") as progress:
            results = downloader.download_batch(
                books_to_download,
                format=format,
                output_dir=output_dir,
                parallel=parallel,
                progress_callback=progress.update,
            )

        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        console.print("[green]Batch download completed[/green]")
        console.print(f"  Successful: {successful}")
        if failed > 0:
            console.print(f"  Failed: {failed}")

    except Exception as e:
        logger.error(f"Batch download failed: {e}")
        console.print(f"[red]Batch download failed: {e}[/red]")
        ctx.exit(1)


@download.command()
@click.option(
    "--url",
    "-u",
    required=True,
    help="Direct URL to download book from.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for downloaded book.",
)
@click.option(
    "--filename",
    "-n",
    help="Custom filename for downloaded book.",
)
@click.pass_context
def url(
    ctx: click.Context,
    url: str,
    output_dir: Optional[Path],
    filename: Optional[str],
) -> None:
    """
    Download book from direct URL.

    Examples:
        book-tool download url -u "https://example.com/book.mobi"
        book-tool download url -u "https://example.com/book.epub" -n "custom_name.epub"
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        downloader = BookDownloader(config.get_download_config())

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would download from URL: {url}[/yellow]")
            if output_dir:
                console.print(f"  Output directory: {output_dir}")
            if filename:
                console.print(f"  Filename: {filename}")
            return

        with ProgressManager("Downloading from URL") as progress:
            result = downloader.download_from_url(
                url,
                output_dir=output_dir,
                filename=filename,
                progress_callback=progress.update,
            )

        if result.success:
            console.print(f"[green]Successfully downloaded: {result.filepath}[/green]")
        else:
            console.print(f"[red]Download failed: {result.error}[/red]")
            ctx.exit(1)

    except Exception as e:
        logger.error(f"URL download failed: {e}")
        console.print(f"[red]URL download failed: {e}[/red]")
        ctx.exit(1)
