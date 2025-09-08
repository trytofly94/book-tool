"""
Library command module for Calibre Books CLI.

This module provides commands for managing Calibre libraries,
including status checks, cleanup, and maintenance operations.
"""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from calibre_books.core.calibre import CalibreIntegration
from calibre_books.utils.progress import ProgressManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def library(ctx: click.Context) -> None:
    """Manage Calibre library operations."""


@library.command()
@click.option(
    "--library",
    "-l",
    type=click.Path(exists=True, path_type=Path),
    help="Path to Calibre library.",
)
@click.option(
    "--detailed",
    "-d",
    is_flag=True,
    help="Show detailed library statistics.",
)
@click.pass_context
def status(
    ctx: click.Context,
    library: Optional[Path],
    detailed: bool,
) -> None:
    """
    Show Calibre library status and statistics.

    Examples:
        book-tool library status
        book-tool library status --library ~/Books --detailed
    """
    config = ctx.obj["config"]

    try:
        calibre = CalibreIntegration(config)

        # Get library statistics
        with ProgressManager("Analyzing library") as progress:
            stats = calibre.get_library_stats(
                library_path=library,
                detailed=detailed,
                progress_callback=progress.update,
            )

        # Basic statistics table
        basic_table = Table(title="Library Overview")
        basic_table.add_column("Metric", style="cyan")
        basic_table.add_column("Value", style="white")

        basic_table.add_row("Total books", str(stats.total_books))
        basic_table.add_row("Total authors", str(stats.total_authors))
        basic_table.add_row("Total series", str(stats.total_series))
        basic_table.add_row("Library size", stats.library_size_human)
        basic_table.add_row("Last updated", stats.last_updated.isoformat())

        console.print(basic_table)

        if detailed:
            # Format distribution
            if stats.format_distribution:
                format_table = Table(title="Format Distribution")
                format_table.add_column("Format", style="cyan")
                format_table.add_column("Count", style="white")
                format_table.add_column("Percentage", style="dim")

                for format_name, count in stats.format_distribution.items():
                    percentage = (count / stats.total_books) * 100
                    format_table.add_row(
                        format_name,
                        str(count),
                        f"{percentage:.1f}%",
                    )

                console.print(format_table)

            # Top authors
            if stats.top_authors:
                author_table = Table(title="Top Authors (by book count)")
                author_table.add_column("Author", style="cyan")
                author_table.add_column("Books", style="white")

                for author, count in stats.top_authors[:10]:  # Top 10
                    author_table.add_row(author, str(count))

                console.print(author_table)

            # Library health indicators
            health_table = Table(title="Library Health")
            health_table.add_column("Indicator", style="cyan")
            health_table.add_column("Status", style="white")

            health_table.add_row(
                "Books without ASIN",
                f"{stats.books_without_asin} ({stats.books_without_asin_percent:.1f}%)",
            )
            health_table.add_row("Duplicate titles", str(stats.duplicate_titles))
            health_table.add_row("Missing covers", str(stats.missing_covers))
            health_table.add_row("Corrupted files", str(stats.corrupted_files))

            console.print(health_table)

    except Exception as e:
        logger.error(f"Failed to get library status: {e}")
        console.print(f"[red]Failed to get library status: {e}[/red]")
        ctx.exit(1)


@library.command()
@click.option(
    "--library",
    "-l",
    type=click.Path(exists=True, path_type=Path),
    help="Path to Calibre library.",
)
@click.option(
    "--remove-duplicates",
    "-d",
    is_flag=True,
    help="Remove duplicate book entries.",
)
@click.option(
    "--fix-metadata",
    "-m",
    is_flag=True,
    help="Fix common metadata issues.",
)
@click.option(
    "--cleanup-files",
    "-f",
    is_flag=True,
    help="Remove orphaned and temporary files.",
)
@click.option(
    "--rebuild-index",
    "-i",
    is_flag=True,
    help="Rebuild search index.",
)
@click.pass_context
def cleanup(
    ctx: click.Context,
    library: Optional[Path],
    remove_duplicates: bool,
    fix_metadata: bool,
    cleanup_files: bool,
    rebuild_index: bool,
) -> None:
    """
    Clean up and optimize Calibre library.

    Examples:
        book-tool library cleanup --remove-duplicates
        book-tool library cleanup --fix-metadata --cleanup-files
        book-tool library cleanup --library ~/Books --rebuild-index
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    if not any([remove_duplicates, fix_metadata, cleanup_files, rebuild_index]):
        console.print(
            "[yellow]No cleanup operations specified. Use --help for options.[/yellow]"
        )
        return

    try:
        calibre = CalibreIntegration(config)

        if dry_run:
            console.print("[yellow]DRY RUN: Would perform library cleanup:[/yellow]")
            if remove_duplicates:
                console.print("  • Remove duplicate book entries")
            if fix_metadata:
                console.print("  • Fix common metadata issues")
            if cleanup_files:
                console.print("  • Remove orphaned and temporary files")
            if rebuild_index:
                console.print("  • Rebuild search index")
            return

        cleanup_results = {}

        if remove_duplicates:
            with ProgressManager("Removing duplicates") as progress:
                result = calibre.remove_duplicates(
                    library_path=library,
                    progress_callback=progress.update,
                )
            cleanup_results["duplicates_removed"] = result.count

        if fix_metadata:
            with ProgressManager("Fixing metadata") as progress:
                result = calibre.fix_metadata_issues(
                    library_path=library,
                    progress_callback=progress.update,
                )
            cleanup_results["metadata_fixed"] = result.count

        if cleanup_files:
            with ProgressManager("Cleaning up files") as progress:
                result = calibre.cleanup_orphaned_files(
                    library_path=library,
                    progress_callback=progress.update,
                )
            cleanup_results["files_cleaned"] = result.count
            cleanup_results["space_freed"] = result.space_freed_human

        if rebuild_index:
            with ProgressManager("Rebuilding search index") as progress:
                calibre.rebuild_search_index(
                    library_path=library,
                    progress_callback=progress.update,
                )
            cleanup_results["index_rebuilt"] = True

        # Display results
        console.print("[green]Library cleanup completed[/green]")

        if "duplicates_removed" in cleanup_results:
            console.print(
                f"  Duplicates removed: {cleanup_results['duplicates_removed']}"
            )

        if "metadata_fixed" in cleanup_results:
            console.print(
                f"  Metadata issues fixed: {cleanup_results['metadata_fixed']}"
            )

        if "files_cleaned" in cleanup_results:
            console.print(
                f"  Orphaned files removed: {cleanup_results['files_cleaned']}"
            )
            console.print(f"  Space freed: {cleanup_results['space_freed']}")

        if cleanup_results.get("index_rebuilt"):
            console.print("  Search index rebuilt successfully")

    except Exception as e:
        logger.error(f"Library cleanup failed: {e}")
        console.print(f"[red]Library cleanup failed: {e}[/red]")
        ctx.exit(1)


@library.command()
@click.option(
    "--source",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Source Calibre library to export from.",
)
@click.option(
    "--destination",
    "-d",
    type=click.Path(path_type=Path),
    required=True,
    help="Destination for exported library.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["calibre", "csv", "json", "xml"]),
    default="calibre",
    help="Export format.",
)
@click.option(
    "--include-files",
    is_flag=True,
    help="Include book files in export (calibre format only).",
)
@click.option(
    "--filter",
    help="Filter books by author/title pattern.",
)
@click.pass_context
def export(
    ctx: click.Context,
    source: Path,
    destination: Path,
    format: str,
    include_files: bool,
    filter: Optional[str],
) -> None:
    """
    Export Calibre library to different formats.

    Examples:
        book-tool library export -s ~/Library -d ~/Backup --format calibre
        book-tool library export -s ~/Library -d library.csv --format csv
        book-tool library export -s ~/Library -d ~/Export --filter "Sanderson"
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        calibre = CalibreIntegration(config)

        if dry_run:
            console.print("[yellow]DRY RUN: Would export library:[/yellow]")
            console.print(f"  Source: {source}")
            console.print(f"  Destination: {destination}")
            console.print(f"  Format: {format}")
            console.print(f"  Include files: {include_files}")
            if filter:
                console.print(f"  Filter: {filter}")
            return

        with ProgressManager("Exporting library") as progress:
            result = calibre.export_library(
                source_path=source,
                destination_path=destination,
                export_format=format,
                include_files=include_files,
                filter_pattern=filter,
                progress_callback=progress.update,
            )

        console.print(f"[green]Library exported successfully[/green]")
        console.print(f"  Books exported: {result.book_count}")
        console.print(f"  Export size: {result.export_size_human}")
        console.print(f"  Location: {result.export_path}")

    except Exception as e:
        logger.error(f"Library export failed: {e}")
        console.print(f"[red]Library export failed: {e}[/red]")
        ctx.exit(1)


@library.command()
@click.option(
    "--library",
    "-l",
    type=click.Path(exists=True, path_type=Path),
    help="Path to Calibre library.",
)
@click.option(
    "--query",
    "-q",
    required=True,
    help="Search query (Calibre search syntax).",
)
@click.option(
    "--limit",
    type=int,
    default=20,
    help="Maximum number of results to show.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "list", "csv"]),
    default="table",
    help="Output format for search results.",
)
@click.pass_context
def search(
    ctx: click.Context,
    library: Optional[Path],
    query: str,
    limit: int,
    format: str,
) -> None:
    """
    Search books in Calibre library.

    Uses Calibre's powerful search syntax. Examples:
        book-tool library search -q "author:Sanderson"
        book-tool library search -q "series:\"Stormlight Archive\""
        book-tool library search -q "tag:fantasy and rating:>=4"
    """
    config = ctx.obj["config"]

    try:
        calibre = CalibreIntegration(config)

        with ProgressManager("Searching library") as progress:
            results = calibre.search_library(
                query=query,
                library_path=library,
                limit=limit,
                progress_callback=progress.update,
            )

        if not results:
            console.print("[yellow]No books found matching query[/yellow]")
            return

        console.print(f"[green]Found {len(results)} books[/green]")

        if format == "table":
            table = Table(title=f"Search Results: '{query}'")
            table.add_column("Title", style="cyan")
            table.add_column("Author", style="white")
            table.add_column("Series", style="dim")
            table.add_column("Rating", style="yellow")

            for book in results:
                table.add_row(
                    book.title,
                    book.author,
                    book.series or "-",
                    str(book.rating) if book.rating else "-",
                )

            console.print(table)

        elif format == "list":
            for book in results:
                console.print(f"• {book.title} by {book.author}")
                if book.series:
                    console.print(f"  Series: {book.series}")
                if book.rating:
                    console.print(f"  Rating: {book.rating}/5")
                console.print()

        elif format == "csv":
            console.print("Title,Author,Series,Rating")
            for book in results:
                console.print(
                    f'"{book.title}","{book.author}","{book.series or ""}","{book.rating or ""}"'
                )

    except Exception as e:
        logger.error(f"Library search failed: {e}")
        console.print(f"[red]Library search failed: {e}[/red]")
        ctx.exit(1)
