"""
Convert command module for Calibre Books CLI.

This module provides commands for converting book formats, including
specialized KFX conversion for Goodreads integration.
"""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from calibre_books.core.converter import FormatConverter
from calibre_books.core.file_scanner import FileScanner
from calibre_books.utils.progress import ProgressManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def convert(ctx: click.Context) -> None:
    """Convert book formats using Calibre."""


@convert.command()
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Directory containing eBook files to convert to KFX.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for KFX files.",
)
@click.option(
    "--parallel",
    "-p",
    type=int,
    default=4,
    help="Number of parallel conversion processes.",
)
@click.option(
    "--check-requirements",
    is_flag=True,
    help="Check system requirements for KFX conversion.",
)
@click.pass_context
def kfx(
    ctx: click.Context,
    input_dir: Path,
    output_dir: Optional[Path],
    parallel: int,
    check_requirements: bool,
) -> None:
    """
    Convert eBook files to KFX format for Goodreads integration.

    This command converts existing eBook files (EPUB, MOBI, AZW3) to KFX format
    optimized for Kindle Goodreads integration with proper metadata preservation.

    Examples:
        book-tool convert kfx --input-dir ./books --parallel 4
        book-tool convert kfx --input-dir ./books --check-requirements
        book-tool convert kfx --input-dir ./mobi_books --output-dir ./kfx_output
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        converter = FormatConverter(config)

        # Check KFX plugin before attempting conversion
        if not converter.validate_kfx_plugin():
            console.print("[red]Error: KFX Output plugin not found![/red]")
            console.print("Please install the KFX Output plugin:")
            console.print("1. Open Calibre → Preferences → Plugins")
            console.print("2. Get new plugins → Search 'KFX Output'")
            console.print("3. Install plugin by jhowell and restart Calibre")
            console.print(
                "\nFor details: https://github.com/trytofly94/book-tool#kfx-conversion-prerequisites"
            )
            raise click.ClickException("KFX Output plugin required for KFX conversion")

        # Check system requirements if requested
        if check_requirements:
            console.print("[cyan]Checking KFX conversion requirements...[/cyan]")
            requirements = converter.check_system_requirements()

            table = Table(title="System Requirements")
            table.add_column("Component", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Description")

            status_map = {
                "calibre": "Calibre GUI application",
                "ebook-convert": "Calibre ebook-convert tool",
                "kfx_plugin": "KFX Output Plugin for Calibre",
                "kindle_previewer": "Kindle Previewer 3",
            }

            for component, available in requirements.items():
                status = "[green]✓[/green]" if available else "[red]✗[/red]"
                description = status_map.get(component, component)
                table.add_row(component, status, description)

            console.print(table)

            missing = [k for k, v in requirements.items() if not v]
            if missing:
                console.print(
                    f"\n[yellow]Missing requirements: {', '.join(missing)}[/yellow]"
                )
                console.print("Please install missing components before conversion.")
            else:
                console.print("\n[green]All requirements satisfied![/green]")

            return

        # Scan for eBook files
        scanner = FileScanner(config)

        with ProgressManager("Scanning for eBook files") as progress:
            books = scanner.scan_directory(
                input_dir,
                recursive=True,
                formats=["mobi", "epub", "azw3", "pdf"],
                check_metadata=False,
                progress_callback=progress.update,
            )

        if not books:
            console.print(
                f"[yellow]No convertible eBook files found in {input_dir}[/yellow]"
            )
            return

        if dry_run:
            console.print(
                f"[yellow]DRY RUN: Would convert {len(books)} books to KFX:[/yellow]"
            )
            console.print(f"  Input directory: {input_dir}")
            console.print(f"  Output directory: {output_dir or './kfx_output'}")
            console.print(f"  Parallel processes: {parallel}")

            for book in books[:5]:  # Show first 5
                console.print(f"    • {book.metadata.title} ({book.format.value})")
            if len(books) > 5:
                console.print(f"    ... and {len(books) - 5} more")
            return

        # Start KFX conversion
        console.print(f"[cyan]Converting {len(books)} books to KFX format...[/cyan]")

        with ProgressManager(f"Converting to KFX") as progress:
            results = converter.convert_batch(
                books,
                output_format="kfx",
                output_dir=output_dir,
                parallel=parallel,
                progress_callback=progress.update,
            )

        # Display results
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        console.print(f"\n[green]KFX conversion completed![/green]")
        console.print(f"  Books processed: {len(books)}")
        console.print(f"  Successful: {successful}")

        if failed > 0:
            console.print(f"  [red]Failed: {failed}[/red]")

            # Show failed conversions
            failed_results = [r for r in results if not r.success]
            if failed_results:
                console.print("\n[red]Failed conversions:[/red]")
                for result in failed_results[:5]:  # Show first 5
                    console.print(f"  • {result.book.metadata.title}: {result.error}")
                if len(failed_results) > 5:
                    console.print(f"    ... and {len(failed_results) - 5} more")

    except Exception as e:
        logger.error(f"KFX conversion failed: {e}")
        console.print(f"[red]KFX conversion failed: {e}[/red]")
        ctx.exit(1)


@convert.command()
@click.option(
    "--input-file",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Single eBook file to convert.",
)
@click.option(
    "--output-file",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["kfx", "azw3", "epub", "mobi", "pdf"]),
    default="kfx",
    help="Target conversion format.",
)
@click.pass_context
def single(
    ctx: click.Context,
    input_file: Path,
    output_file: Optional[Path],
    format: str,
) -> None:
    """
    Convert a single eBook file.

    Examples:
        book-tool convert single -i book.epub -f kfx
        book-tool convert single -i book.mobi -o book_kfx.azw3 -f kfx
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        # Create output filename if not specified
        if not output_file:
            suffix = ".azw3" if format == "kfx" else f".{format}"
            output_file = input_file.parent / f"{input_file.stem}_converted{suffix}"

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would convert:[/yellow]")
            console.print(f"  Input: {input_file}")
            console.print(f"  Output: {output_file}")
            console.print(f"  Format: {format}")
            return

        if format == "kfx":
            # Use KFX converter
            converter = FormatConverter(config)

            # Check KFX plugin before attempting conversion
            if not converter.validate_kfx_plugin():
                console.print("[red]Error: KFX Output plugin not found![/red]")
                console.print("Please install the KFX Output plugin:")
                console.print("1. Open Calibre → Preferences → Plugins")
                console.print("2. Get new plugins → Search 'KFX Output'")
                console.print("3. Install plugin by jhowell and restart Calibre")
                console.print(
                    "\nFor details: https://github.com/trytofly94/book-tool#kfx-conversion-prerequisites"
                )
                raise click.ClickException(
                    "KFX Output plugin required for KFX conversion"
                )

            # Create a Book object from the file
            scanner = FileScanner(config)
            book = scanner._create_book_from_file(input_file, extract_metadata=True)

            if not book:
                console.print(f"[red]Could not process file: {input_file}[/red]")
                ctx.exit(1)

            console.print(f"Converting {book.metadata.title} to KFX...")

            with ProgressManager("Converting to KFX") as progress:
                results = converter.convert_batch(
                    [book],
                    output_format="kfx",
                    output_dir=output_file.parent,
                    parallel=1,
                    progress_callback=progress.update,
                )

            if results and results[0].success:
                console.print(
                    f"[green]✓ Conversion successful: {results[0].output_path}[/green]"
                )
            else:
                error = results[0].error if results else "Unknown error"
                console.print(f"[red]✗ Conversion failed: {error}[/red]")
                ctx.exit(1)
        else:
            # Use standard ebook-convert for other formats
            import subprocess

            cmd = [
                "ebook-convert",
                str(input_file),
                str(output_file),
                "--output-profile",
                "generic_eink" if format == "epub" else "kindle_fire",
            ]

            console.print(f"Converting to {format.upper()}...")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                console.print(f"[green]✓ Conversion successful: {output_file}[/green]")
            else:
                console.print(f"[red]✗ Conversion failed: {result.stderr}[/red]")
                ctx.exit(1)

    except Exception as e:
        logger.error(f"Single file conversion failed: {e}")
        console.print(f"[red]Conversion failed: {e}[/red]")
        ctx.exit(1)
