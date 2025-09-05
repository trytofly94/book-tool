"""
Convert command module for Calibre Books CLI.

This module provides commands for converting book formats, including
specialized KFX conversion for Goodreads integration.
"""

import logging
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table

from calibre_books.core.converter import FormatConverter
from calibre_books.utils.progress import ProgressManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def convert(ctx: click.Context) -> None:
    """Convert book formats using Calibre."""
    pass


@convert.command()
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Directory containing KFX files to convert.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for converted files.",
)
@click.option(
    "--parallel",
    "-p",
    type=int,
    default=4,
    help="Number of parallel conversion processes.",
)
@click.option(
    "--output-format",
    "-f",
    type=click.Choice(["epub", "mobi", "azw3", "pdf"]),
    default="epub",
    help="Target format for conversion.",
)
@click.option(
    "--quality",
    type=click.Choice(["high", "medium", "low"]),
    default="high",
    help="Conversion quality setting.",
)
@click.option(
    "--preserve-metadata",
    "-m",
    is_flag=True,
    default=True,
    help="Preserve original metadata during conversion.",
)
@click.pass_context
def kfx(
    ctx: click.Context,
    input_dir: Path,
    output_dir: Optional[Path],
    parallel: int,
    output_format: str,
    quality: str,
    preserve_metadata: bool,
) -> None:
    """
    Convert KFX files to other formats for Goodreads integration.
    
    This command specializes in converting KFX format books to formats
    compatible with Goodreads reading tracking and other services.
    
    Examples:
        calibre-books convert kfx --input-dir ./kfx_books --parallel 4
        calibre-books convert kfx --input-dir ./books --output-format epub
        calibre-books convert kfx --input-dir ./books --quality high
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]
    
    try:
        converter = FormatConverter(config.get_conversion_config())
        
        # Find all KFX files in input directory
        kfx_files = list(input_dir.glob("**/*.kfx"))
        if not kfx_files:
            console.print(f"[yellow]No KFX files found in {input_dir}[/yellow]")
            return
        
        if dry_run:
            console.print(f"[yellow]DRY RUN: Would convert {len(kfx_files)} KFX files:[/yellow]")
            console.print(f"  Input directory: {input_dir}")
            console.print(f"  Output directory: {output_dir or 'same as input'}")
            console.print(f"  Output format: {output_format}")
            console.print(f"  Parallel processes: {parallel}")
            console.print(f"  Quality: {quality}")
            console.print(f"  Preserve metadata: {preserve_metadata}")
            
            for kfx_file in kfx_files[:5]:  # Show first 5
                console.print(f"    • {kfx_file.name}")
            if len(kfx_files) > 5:
                console.print(f"    ... and {len(kfx_files) - 5} more")
            return
        
        # Validate KFX plugin availability
        if not converter.validate_kfx_plugin():
            console.print("[red]Error: KFX Input plugin not found in Calibre[/red]")
            console.print("Please install the KFX Input plugin first.")
            ctx.exit(1)
        
        # Start conversion with progress tracking
        with ProgressManager(f"Converting {len(kfx_files)} KFX files") as progress:
            results = converter.convert_kfx_batch(
                kfx_files,
                output_dir=output_dir,
                output_format=output_format,
                parallel=parallel,
                quality=quality,
                preserve_metadata=preserve_metadata,
                progress_callback=progress.update,
            )
        
        # Display results
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        console.print(f"[green]KFX conversion completed[/green]")
        console.print(f"  Files processed: {len(kfx_files)}")
        console.print(f"  Successful: {successful}")
        
        if failed > 0:
            console.print(f"  [red]Failed: {failed}[/red]")
            
            # Show failed files
            failed_files = [r for r in results if not r.success]
            if failed_files:
                console.print("\nFailed conversions:")
                for result in failed_files[:5]:  # Show first 5
                    console.print(f"  • {result.input_file}: {result.error}")
        
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
    help="Input book file to convert.",
)
@click.option(
    "--output-file",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (auto-generated if not specified).",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["epub", "mobi", "azw3", "pdf", "txt"]),
    required=True,
    help="Target format for conversion.",
)
@click.option(
    "--quality",
    type=click.Choice(["high", "medium", "low"]),
    default="high",
    help="Conversion quality setting.",
)
@click.option(
    "--cover/--no-cover",
    default=True,
    help="Include/exclude cover image.",
)
@click.option(
    "--metadata/--no-metadata",
    default=True,
    help="Preserve/strip metadata.",
)
@click.pass_context
def single(
    ctx: click.Context,
    input_file: Path,
    output_file: Optional[Path],
    format: str,
    quality: str,
    cover: bool,
    metadata: bool,
) -> None:
    """
    Convert a single book file to another format.
    
    Examples:
        calibre-books convert single -i book.mobi -f epub
        calibre-books convert single -i book.pdf -f txt --no-cover
        calibre-books convert single -i book.kfx -o custom_name.epub -f epub
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]
    
    try:
        converter = FormatConverter(config.get_conversion_config())
        
        if dry_run:
            console.print("[yellow]DRY RUN: Would convert single file:[/yellow]")
            console.print(f"  Input: {input_file}")
            console.print(f"  Output: {output_file or 'auto-generated'}")
            console.print(f"  Format: {format}")
            console.print(f"  Quality: {quality}")
            console.print(f"  Include cover: {cover}")
            console.print(f"  Preserve metadata: {metadata}")
            return
        
        with ProgressManager("Converting book") as progress:
            result = converter.convert_single(
                input_file,
                output_file=output_file,
                output_format=format,
                quality=quality,
                include_cover=cover,
                preserve_metadata=metadata,
                progress_callback=progress.update,
            )
        
        if result.success:
            console.print(f"[green]Successfully converted to: {result.output_file}[/green]")
            
            # Show file size information
            if result.file_size:
                console.print(f"  Output size: {result.file_size}")
        else:
            console.print(f"[red]Conversion failed: {result.error}[/red]")
            ctx.exit(1)
            
    except Exception as e:
        logger.error(f"Single file conversion failed: {e}")
        console.print(f"[red]Conversion failed: {e}[/red]")
        ctx.exit(1)


@convert.command()
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Directory containing files to convert.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for converted files.",
)
@click.option(
    "--from-format",
    type=click.Choice(["mobi", "epub", "pdf", "azw3", "kfx"]),
    help="Source format filter (convert only these files).",
)
@click.option(
    "--to-format",
    "-f",
    type=click.Choice(["epub", "mobi", "azw3", "pdf", "txt"]),
    required=True,
    help="Target format for conversion.",
)
@click.option(
    "--parallel",
    "-p",
    type=int,
    default=2,
    help="Number of parallel conversion processes.",
)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    help="Search subdirectories recursively.",
)
@click.pass_context
def batch(
    ctx: click.Context,
    input_dir: Path,
    output_dir: Optional[Path],
    from_format: Optional[str],
    to_format: str,
    parallel: int,
    recursive: bool,
) -> None:
    """
    Convert multiple book files in a directory.
    
    Examples:
        calibre-books convert batch -i ./books -f epub --recursive
        calibre-books convert batch -i ./mobi_books --from-format mobi -f epub
        calibre-books convert batch -i ./books -o ./converted --parallel 4 -f pdf
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]
    
    try:
        converter = FormatConverter(config.get_conversion_config())
        
        # Find all files to convert
        files_to_convert = converter.find_convertible_files(
            input_dir,
            source_format=from_format,
            recursive=recursive,
        )
        
        if not files_to_convert:
            console.print(f"[yellow]No convertible files found in {input_dir}[/yellow]")
            return
        
        if dry_run:
            console.print(f"[yellow]DRY RUN: Would convert {len(files_to_convert)} files:[/yellow]")
            console.print(f"  Input directory: {input_dir}")
            console.print(f"  Output directory: {output_dir or 'same as input'}")
            console.print(f"  Source format: {from_format or 'all supported'}")
            console.print(f"  Target format: {to_format}")
            console.print(f"  Parallel processes: {parallel}")
            console.print(f"  Recursive: {recursive}")
            
            for file in files_to_convert[:5]:  # Show first 5
                console.print(f"    • {file.name}")
            if len(files_to_convert) > 5:
                console.print(f"    ... and {len(files_to_convert) - 5} more")
            return
        
        # Start batch conversion
        with ProgressManager(f"Converting {len(files_to_convert)} files") as progress:
            results = converter.convert_batch(
                files_to_convert,
                output_dir=output_dir,
                output_format=to_format,
                parallel=parallel,
                progress_callback=progress.update,
            )
        
        # Display results
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        console.print(f"[green]Batch conversion completed[/green]")
        console.print(f"  Files processed: {len(files_to_convert)}")
        console.print(f"  Successful: {successful}")
        
        if failed > 0:
            console.print(f"  [red]Failed: {failed}[/red]")
            
    except Exception as e:
        logger.error(f"Batch conversion failed: {e}")
        console.print(f"[red]Batch conversion failed: {e}[/red]")
        ctx.exit(1)


@convert.command()
@click.pass_context
def formats(ctx: click.Context) -> None:
    """Show supported input and output formats."""
    config = ctx.obj["config"]
    
    try:
        converter = FormatConverter(config.get_conversion_config())
        supported_formats = converter.get_supported_formats()
        
        # Input formats table
        input_table = Table(title="Supported Input Formats")
        input_table.add_column("Format", style="cyan")
        input_table.add_column("Extension", style="white")
        input_table.add_column("Description", style="dim")
        
        for fmt in supported_formats.input_formats:
            input_table.add_row(
                fmt.name,
                fmt.extension,
                fmt.description,
            )
        
        console.print(input_table)
        
        # Output formats table  
        output_table = Table(title="Supported Output Formats")
        output_table.add_column("Format", style="cyan")
        output_table.add_column("Extension", style="white")
        output_table.add_column("Description", style="dim")
        
        for fmt in supported_formats.output_formats:
            output_table.add_row(
                fmt.name,
                fmt.extension,
                fmt.description,
            )
        
        console.print(output_table)
        
    except Exception as e:
        logger.error(f"Failed to get supported formats: {e}")
        console.print(f"[red]Failed to get supported formats: {e}[/red]")
        ctx.exit(1)