"""
ASIN command module for Calibre Books CLI.

This module provides commands for managing ASINs and book metadata,
including lookup, batch updates, and cache management.
"""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from calibre_books.core.asin_lookup import ASINLookupService
from calibre_books.core.calibre import CalibreIntegration
from calibre_books.utils.progress import ProgressManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def asin(ctx: click.Context) -> None:
    """Manage ASINs and book metadata."""


@asin.command()
@click.option(
    "--book",
    "-b",
    help="Book title to lookup ASIN for.",
)
@click.option(
    "--author",
    "-a",
    help="Book author (improves lookup accuracy).",
)
@click.option(
    "--isbn",
    "-i",
    help="Book ISBN for lookup.",
)
@click.option(
    "--sources",
    "-s",
    multiple=True,
    type=click.Choice(["amazon", "goodreads", "openlibrary"]),
    help="ASIN lookup sources to use.",
)
@click.option(
    "--cache/--no-cache",
    default=True,
    help="Use cached results when available.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output for debugging ASIN lookup issues.",
)
@click.option(
    "--fuzzy/--no-fuzzy",
    default=True,
    help="Enable fuzzy matching and title variations for improved success rate.",
)
@click.option(
    "--fuzzy-threshold",
    type=int,
    default=80,
    help="Fuzzy matching similarity threshold (0-100, default: 80).",
)
@click.pass_context
def lookup(
    ctx: click.Context,
    book: Optional[str],
    author: Optional[str],
    isbn: Optional[str],
    sources: tuple[str, ...],
    cache: bool,
    verbose: bool,
    fuzzy: bool,
    fuzzy_threshold: int,
) -> None:
    """
    Look up ASIN for a specific book.

    Examples:
        book-tool asin lookup --book "The Way of Kings" --author "Brandon Sanderson"
        book-tool asin lookup --isbn "9780765326355"
        book-tool asin lookup --book "Dune" --sources amazon goodreads
        book-tool asin lookup --book "Mistborn" --author "Sanderson" --fuzzy --verbose
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    if not any([book, isbn]):
        console.print("[red]Error: Must specify either --book or --isbn[/red]")
        ctx.exit(1)

    try:
        lookup_service = ASINLookupService(config)

        # Configure enhanced search features (Issue #55)
        lookup_service.enable_series_variations = fuzzy
        lookup_service.enable_fuzzy_matching = fuzzy
        lookup_service.fuzzy_threshold = fuzzy_threshold

        if dry_run:
            console.print("[yellow]DRY RUN: Would lookup ASIN for:[/yellow]")
            if book:
                console.print(f"  Book: {book}")
            if author:
                console.print(f"  Author: {author}")
            if isbn:
                console.print(f"  ISBN: {isbn}")
            console.print(f"  Sources: {sources if sources else 'default'}")
            console.print(f"  Use cache: {cache}")
            return

        # Set verbose mode for debugging
        if verbose:
            # Enable debug logging for ASIN lookup
            asin_logger = logging.getLogger("calibre_books.core.asin_lookup")
            asin_logger.setLevel(logging.DEBUG)
            console.print(
                "[yellow]Verbose mode enabled - showing detailed lookup information[/yellow]"
            )
            if fuzzy:
                console.print(
                    f"[cyan]Enhanced search enabled - fuzzy matching threshold: {fuzzy_threshold}%[/cyan]"
                )
            else:
                console.print(
                    "[dim]Enhanced search disabled - using exact matching only[/dim]"
                )

        with ProgressManager("Looking up ASIN") as progress:
            if isbn:
                result = lookup_service.lookup_by_isbn(
                    isbn,
                    sources=sources or None,
                    use_cache=cache,
                    progress_callback=progress.update,
                    verbose=verbose,
                )
            else:
                result = lookup_service.lookup_by_title(
                    book,
                    author=author,
                    sources=sources or None,
                    use_cache=cache,
                    progress_callback=progress.update,
                    verbose=verbose,
                )

        if result.asin:
            console.print(f"[green]ASIN found: {result.asin}[/green]")
            if result.source:
                console.print(f"[cyan]Source: {result.source}[/cyan]")
            if result.lookup_time:
                console.print(f"[dim]Lookup time: {result.lookup_time:.2f}s[/dim]")
            if result.from_cache:
                console.print("[dim](from cache)[/dim]")

            # Display additional metadata if available (but not error metadata)
            if (
                result.metadata
                and isinstance(result.metadata, dict)
                and not all(isinstance(v, str) for v in result.metadata.values())
            ):
                table = Table(title="Book Metadata")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="white")

                for field, value in result.metadata.items():
                    table.add_row(field, str(value))

                console.print(table)
        else:
            console.print("[yellow]No ASIN found[/yellow]")
            if result.error:
                console.print(f"[red]Error: {result.error}[/red]")

            # In verbose mode, show detailed error information
            if verbose and result.metadata and isinstance(result.metadata, dict):
                console.print("\n[yellow]Detailed source information:[/yellow]")
                error_table = Table(title="Source Lookup Results")
                error_table.add_column("Source", style="cyan")
                error_table.add_column("Result", style="white")

                for source, error in result.metadata.items():
                    error_table.add_row(source, str(error))

                console.print(error_table)

            if result.lookup_time:
                console.print(
                    f"[dim]Total lookup time: {result.lookup_time:.2f}s[/dim]"
                )

    except Exception as e:
        logger.error(f"ASIN lookup failed: {e}")
        console.print(f"[red]ASIN lookup failed: {e}[/red]")
        ctx.exit(1)


@asin.command()
@click.option(
    "--library",
    "-l",
    type=click.Path(exists=True, path_type=Path),
    help="Path to Calibre library.",
)
@click.option(
    "--filter",
    "-f",
    help="Filter books by title/author pattern.",
)
@click.option(
    "--missing-only",
    "-m",
    is_flag=True,
    help="Only update books without ASINs.",
)
@click.option(
    "--parallel",
    "-p",
    type=int,
    default=2,
    help="Number of parallel lookup requests.",
)
@click.option(
    "--sources",
    "-s",
    multiple=True,
    type=click.Choice(["amazon", "goodreads", "openlibrary"]),
    help="ASIN lookup sources to use.",
)
@click.pass_context
def batch_update(
    ctx: click.Context,
    library: Optional[Path],
    filter: Optional[str],
    missing_only: bool,
    parallel: int,
    sources: tuple[str, ...],
) -> None:
    """
    Update ASINs for multiple books in Calibre library.

    Examples:
        book-tool asin batch-update --library ~/Calibre-Library --missing-only
        book-tool asin batch-update --filter "Sanderson" --parallel 4
        book-tool asin batch-update --sources amazon goodreads
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        calibre = CalibreIntegration(config)
        lookup_service = ASINLookupService(config)

        # Get list of books to process
        books_to_process = calibre.get_books_for_asin_update(
            library_path=library,
            filter_pattern=filter,
            missing_only=missing_only,
        )

        if not books_to_process:
            console.print("[yellow]No books found matching criteria[/yellow]")
            return

        if dry_run:
            console.print(
                f"[yellow]DRY RUN: Would update ASINs for {len(books_to_process)} books:[/yellow]"
            )
            for book in books_to_process[:5]:  # Show first 5
                console.print(f"  • {book.title} by {book.author}")
            if len(books_to_process) > 5:
                console.print(f"  ... and {len(books_to_process) - 5} more")
            return

        # Start batch ASIN update
        with ProgressManager(
            f"Updating ASINs for {len(books_to_process)} books"
        ) as progress:
            results = lookup_service.batch_update(
                books_to_process,
                sources=sources or None,
                parallel=parallel,
                progress_callback=progress.update,
            )

        # Update Calibre library with new ASINs
        updated_count = calibre.update_asins(results)

        console.print("[green]Batch ASIN update completed[/green]")
        console.print(f"  Books processed: {len(books_to_process)}")
        console.print(f"  ASINs found: {sum(1 for r in results if r.asin)}")
        console.print(f"  Library updated: {updated_count}")

    except Exception as e:
        logger.error(f"Batch ASIN update failed: {e}")
        console.print(f"[red]Batch ASIN update failed: {e}[/red]")
        ctx.exit(1)


@asin.command()
@click.option(
    "--show-stats",
    "-s",
    is_flag=True,
    help="Show cache statistics.",
)
@click.option(
    "--clear",
    "-c",
    is_flag=True,
    help="Clear all cached ASINs.",
)
@click.option(
    "--cleanup",
    is_flag=True,
    help="Remove expired cache entries.",
)
@click.pass_context
def cache(
    ctx: click.Context,
    show_stats: bool,
    clear: bool,
    cleanup: bool,
) -> None:
    """
    Manage ASIN lookup cache.

    Examples:
        book-tool asin cache --show-stats
        book-tool asin cache --cleanup
        book-tool asin cache --clear
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        lookup_service = ASINLookupService(config)
        cache_manager = lookup_service.cache_manager

        if show_stats:
            stats = cache_manager.get_stats()

            table = Table(title="ASIN Cache Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Total entries", str(stats.total_entries))
            table.add_row("Hit rate", f"{stats.hit_rate:.1%}")
            table.add_row("Cache size", stats.size_human)
            table.add_row("Last updated", stats.last_updated.isoformat())

            console.print(table)

        if clear:
            if dry_run:
                console.print("[yellow]DRY RUN: Would clear ASIN cache[/yellow]")
                return

            cache_manager.clear()
            console.print("[green]ASIN cache cleared[/green]")

        if cleanup:
            if dry_run:
                console.print(
                    "[yellow]DRY RUN: Would cleanup expired cache entries[/yellow]"
                )
                return

            removed_count = cache_manager.cleanup_expired()
            console.print(
                f"[green]Removed {removed_count} expired cache entries[/green]"
            )

        if not any([show_stats, clear, cleanup]):
            console.print("Use --show-stats, --clear, or --cleanup")

    except Exception as e:
        logger.error(f"Cache operation failed: {e}")
        console.print(f"[red]Cache operation failed: {e}[/red]")
        ctx.exit(1)


@asin.command()
@click.option(
    "--asin",
    "-a",
    required=True,
    help="ASIN to verify.",
)
@click.option(
    "--check-availability",
    "-c",
    is_flag=True,
    help="Check if ASIN is still available on Amazon.",
)
@click.pass_context
def verify(
    ctx: click.Context,
    asin: str,
    check_availability: bool,
) -> None:
    """
    Verify ASIN format and optionally check availability.

    Examples:
        book-tool asin verify --asin B00ZVA3XL6
        book-tool asin verify --asin B00ZVA3XL6 --check-availability
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        lookup_service = ASINLookupService(config)

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would verify ASIN: {asin}[/yellow]")
            if check_availability:
                console.print("  Would check availability on Amazon")
            return

        # Validate ASIN format
        is_valid = lookup_service.validate_asin(asin)

        if is_valid:
            console.print(f"[green]ASIN format is valid: {asin}[/green]")

            if check_availability:
                with ProgressManager("Checking availability") as progress:
                    availability = lookup_service.check_availability(
                        asin,
                        progress_callback=progress.update,
                    )

                if availability.available:
                    console.print("[green]ASIN is available on Amazon[/green]")
                    if availability.metadata:
                        console.print(
                            f"  Title: {availability.metadata.get('title', 'N/A')}"
                        )
                        console.print(
                            f"  Price: {availability.metadata.get('price', 'N/A')}"
                        )
                else:
                    console.print("[red]ASIN is not available or restricted[/red]")
        else:
            console.print(f"[red]Invalid ASIN format: {asin}[/red]")
            ctx.exit(1)

    except Exception as e:
        logger.error(f"ASIN verification failed: {e}")
        console.print(f"[red]ASIN verification failed: {e}[/red]")
        ctx.exit(1)
