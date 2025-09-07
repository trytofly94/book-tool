"""
Process command module for Calibre Books CLI.

This module provides commands for processing existing eBook files,
including file discovery, format analysis, and batch operations.
"""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from calibre_books.utils.progress import ProgressManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def process(ctx: click.Context) -> None:
    """Process existing eBook files."""
    pass


@process.command()
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Directory containing eBook files.",
)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    help="Scan directories recursively.",
)
@click.option(
    "--format",
    "-f",
    help="Filter by format (comma-separated, e.g., 'mobi,epub').",
)
@click.option(
    "--output-json",
    "-o",
    type=click.Path(path_type=Path),
    help="Output scan results to JSON file.",
)
@click.option(
    "--check-asin",
    is_flag=True,
    help="Check if files have ASIN metadata.",
)
@click.option(
    "--validate-first",
    is_flag=True,
    help="Validate files before processing to detect corruption/issues.",
)
@click.pass_context
def scan(
    ctx: click.Context,
    input_dir: Path,
    recursive: bool,
    format: Optional[str],
    output_json: Optional[Path],
    check_asin: bool,
    validate_first: bool,
) -> None:
    """
    Scan directory for existing eBook files.
    
    Examples:
        book-tool process scan --input-dir ./books
        book-tool process scan --input-dir ~/Downloads --format mobi
        book-tool process scan --recursive --format "mobi,epub"
        book-tool process scan --input-dir ./books --validate-first
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]
    
    try:
        from calibre_books.core.file_scanner import FileScanner
        scanner = FileScanner(config)
        
        if dry_run:
            console.print("[yellow]DRY RUN: Would scan directory:[/yellow]")
            console.print(f"  Directory: {input_dir}")
            console.print(f"  Recursive: {recursive}")
            if format:
                console.print(f"  Formats: {format}")
            console.print(f"  Check ASIN: {check_asin}")
            console.print(f"  Validate first: {validate_first}")
            return
        
        # Parse format filter
        formats = format.split(',') if format else None
        
        # Validate files first if requested
        if validate_first:
            from calibre_books.core.file_validator import FileValidator
            
            console.print("[cyan]Validating files before processing...[/cyan]")
            validator = FileValidator(config.get_config())
            
            with ProgressManager("Validating eBook files") as validation_progress:
                validation_results = validator.validate_directory(
                    input_dir,
                    recursive=recursive,
                    formats=formats,
                    use_cache=True,
                    progress_callback=validation_progress.update,
                    parallel=True,
                )
            
            # Check for validation failures
            failed_files = [r for r in validation_results if not r.is_valid]
            if failed_files:
                console.print(f"[red]Found {len(failed_files)} invalid files:[/red]")
                for result in failed_files[:5]:  # Show first 5
                    console.print(f"  ✗ {result.file_path.name}: {'; '.join(result.errors)}")
                
                if len(failed_files) > 5:
                    console.print(f"  ... and {len(failed_files) - 5} more")
                
                console.print(f"\n[yellow]Continuing with {len(validation_results) - len(failed_files)} valid files...[/yellow]")
            else:
                console.print(f"[green]All {len(validation_results)} files validated successfully[/green]")
        
        # Scan for eBook files
        with ProgressManager("Scanning for eBook files") as progress:
            results = scanner.scan_directory(
                input_dir,
                recursive=recursive,
                formats=formats,
                check_metadata=check_asin,
                progress_callback=progress.update,
            )
        
        if results:
            console.print(f"[green]Found {len(results)} eBook files[/green]")
            
            # Group by format
            by_format = {}
            for book in results:
                fmt = book.format.upper()
                by_format[fmt] = by_format.get(fmt, 0) + 1
            
            for fmt, count in sorted(by_format.items()):
                console.print(f"  • {fmt}: {count} files")
            
            if check_asin:
                with_asin = sum(1 for b in results if b.has_asin)
                without_asin = len(results) - with_asin
                console.print(f"\n[cyan]ASIN Status:[/cyan]")
                console.print(f"  • With ASIN: {with_asin}")
                console.print(f"  • Without ASIN: {without_asin}")
            
            # Save to JSON if requested
            if output_json:
                scanner.save_results(results, output_json)
                console.print(f"\n[green]Results saved to: {output_json}[/green]")
        else:
            console.print("[yellow]No eBook files found[/yellow]")
            
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        console.print(f"[red]Scan failed: {e}[/red]")
        ctx.exit(1)


@process.command()
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Directory containing eBook files to prepare.",
)
@click.option(
    "--add-asin",
    is_flag=True,
    help="Add ASIN metadata to files.",
)
@click.option(
    "--lookup",
    is_flag=True,
    help="Automatically lookup ASINs online.",
)
@click.option(
    "--check-only",
    is_flag=True,
    help="Only check ASIN status, don't modify files.",
)
@click.option(
    "--validate-first",
    is_flag=True,
    help="Validate files before processing to detect corruption/issues.",
)
@click.pass_context
def prepare(
    ctx: click.Context,
    input_dir: Path,
    add_asin: bool,
    lookup: bool,
    check_only: bool,
    validate_first: bool,
) -> None:
    """
    Prepare eBook files for Goodreads integration.
    
    This command processes existing files to add ASIN metadata
    and prepare them for Kindle/Goodreads sync.
    
    Examples:
        book-tool process prepare -i ./books --add-asin --lookup
        book-tool process prepare -i ./books --check-only
        book-tool process prepare -i ./books --validate-first --add-asin
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]
    
    try:
        from calibre_books.core.file_scanner import FileScanner
        from calibre_books.core.asin_manager import ASINManager
        
        scanner = FileScanner(config)
        asin_manager = ASINManager(config)
        
        if dry_run:
            console.print(f"[yellow]DRY RUN: Would prepare files in: {input_dir}[/yellow]")
            console.print(f"  Add ASIN: {add_asin}")
            console.print(f"  Lookup online: {lookup}")
            console.print(f"  Check only: {check_only}")
            console.print(f"  Validate first: {validate_first}")
            return
        
        # Validate files first if requested
        if validate_first:
            from calibre_books.core.file_validator import FileValidator
            
            console.print("[cyan]Validating files before processing...[/cyan]")
            validator = FileValidator(config.get_config())
            
            with ProgressManager("Validating eBook files") as validation_progress:
                validation_results = validator.validate_directory(
                    input_dir,
                    recursive=True,
                    use_cache=True,
                    progress_callback=validation_progress.update,
                    parallel=True,
                )
            
            # Check for validation failures and abort if too many
            failed_files = [r for r in validation_results if not r.is_valid]
            if failed_files:
                console.print(f"[red]Found {len(failed_files)} invalid files:[/red]")
                for result in failed_files[:5]:  # Show first 5
                    console.print(f"  ✗ {result.file_path.name}: {'; '.join(result.errors)}")
                
                if len(failed_files) > 5:
                    console.print(f"  ... and {len(failed_files) - 5} more")
                
                # Only continue if the majority of files are valid
                if len(failed_files) > len(validation_results) / 2:
                    console.print("[red]Too many invalid files found. Aborting to prevent wasted processing.[/red]")
                    console.print("[yellow]Use 'book-tool validate scan' to see detailed validation report.[/yellow]")
                    ctx.exit(1)
                
                console.print(f"\n[yellow]Continuing with {len(validation_results) - len(failed_files)} valid files...[/yellow]")
            else:
                console.print(f"[green]All {len(validation_results)} files validated successfully[/green]")
        
        # Scan for eBook files
        with ProgressManager("Scanning eBook files") as progress:
            books = scanner.scan_directory(
                input_dir,
                recursive=True,
                check_metadata=True,
                progress_callback=progress.update,
            )
        
        if not books:
            console.print("[yellow]No eBook files found[/yellow]")
            return
        
        # Filter books without ASIN
        books_without_asin = [b for b in books if not b.has_asin]
        
        console.print(f"\n[cyan]Found {len(books)} books:[/cyan]")
        console.print(f"  • With ASIN: {len(books) - len(books_without_asin)}")
        console.print(f"  • Without ASIN: {len(books_without_asin)}")
        
        if check_only:
            # Just report status
            if books_without_asin:
                console.print("\n[yellow]Books without ASIN:[/yellow]")
                for book in books_without_asin[:10]:
                    console.print(f"  • {book.metadata.title} by {book.metadata.author}")
                if len(books_without_asin) > 10:
                    console.print(f"  ... and {len(books_without_asin) - 10} more")
            return
        
        if add_asin and books_without_asin:
            console.print(f"\n[cyan]Processing {len(books_without_asin)} books without ASIN...[/cyan]")
            
            with ProgressManager(f"Adding ASINs to {len(books_without_asin)} books") as progress:
                results = asin_manager.process_books(
                    books_without_asin,
                    lookup_online=lookup,
                    progress_callback=progress.update,
                )
            
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            
            console.print(f"\n[green]ASIN processing completed:[/green]")
            console.print(f"  • Successful: {successful}")
            if failed > 0:
                console.print(f"  • Failed: {failed}")
            
    except Exception as e:
        logger.error(f"Prepare failed: {e}")
        console.print(f"[red]Prepare failed: {e}[/red]")
        ctx.exit(1)