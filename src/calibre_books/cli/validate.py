"""
Validate command module for Calibre Books CLI.

This module provides commands for validating eBook files to detect
corrupted files, extension mismatches, and other integrity issues.
"""

import logging
from pathlib import Path
from typing import Optional, List

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from ..core.file_validator import FileValidator
from ..utils.validation import ValidationStatus
from ..utils.progress import ProgressManager

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate eBook files for corruption and format issues."""


@validate.command()
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Directory containing eBook files to validate.",
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
    help="Output validation results to JSON file.",
)
@click.option(
    "--parallel",
    "-p",
    is_flag=True,
    help="Use parallel validation for better performance.",
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=4,
    help="Number of worker threads for parallel validation (default: 4).",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable validation caching.",
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Clear validation cache before running.",
)
@click.option(
    "--details",
    is_flag=True,
    help="Include detailed validation information in output.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Quiet mode - only show summary and errors.",
)
@click.pass_context
def scan(
    ctx: click.Context,
    input_dir: Path,
    recursive: bool,
    format: Optional[str],
    output_json: Optional[Path],
    parallel: bool,
    workers: int,
    no_cache: bool,
    clear_cache: bool,
    details: bool,
    quiet: bool,
) -> None:
    """
    Scan and validate eBook files in a directory.

    This command performs comprehensive validation of eBook files,
    detecting corrupted files, extension mismatches, and format issues.

    Examples:
        book-tool validate scan --input-dir ./books
        book-tool validate scan --input-dir ~/Downloads --format epub --parallel
        book-tool validate scan --recursive --output-json validation_report.json
        book-tool validate scan --input-dir ./books --clear-cache --no-cache
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        validator = FileValidator(config.get_config())

        # Clear cache if requested
        if clear_cache:
            validator.clear_cache()
            if not quiet:
                console.print("[yellow]Validation cache cleared[/yellow]")

        if dry_run:
            console.print("[yellow]DRY RUN: Would validate files in:[/yellow]")
            console.print(f"  Directory: {input_dir}")
            console.print(f"  Recursive: {recursive}")
            if format:
                console.print(f"  Formats: {format}")
            console.print(f"  Parallel: {parallel} (workers: {workers})")
            console.print(f"  Use cache: {not no_cache}")
            return

        # Parse format filter
        formats = format.split(",") if format else None

        # Perform validation
        results = []
        if quiet:
            # No progress display in quiet mode
            results = validator.validate_directory(
                input_dir,
                recursive=recursive,
                formats=formats,
                use_cache=not no_cache,
                progress_callback=None,
                parallel=parallel,
                max_workers=workers,
            )
        else:
            with ProgressManager("Validating eBook files") as progress:
                results = validator.validate_directory(
                    input_dir,
                    recursive=recursive,
                    formats=formats,
                    use_cache=not no_cache,
                    progress_callback=progress.update,
                    parallel=parallel,
                    max_workers=workers,
                )

        # Display results
        if results:
            _display_validation_results(results, details, quiet)

            # Save to JSON if requested
            if output_json:
                validator.save_results(results, output_json, include_details=details)
                if not quiet:
                    console.print(f"\n[green]Results saved to: {output_json}[/green]")
        else:
            console.print("[yellow]No eBook files found[/yellow]")

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        console.print(f"[red]Validation failed: {e}[/red]")
        ctx.exit(1)


@validate.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable validation caching.",
)
@click.option(
    "--details",
    is_flag=True,
    help="Show detailed validation information.",
)
@click.pass_context
def file(
    ctx: click.Context,
    file_path: Path,
    no_cache: bool,
    details: bool,
) -> None:
    """
    Validate a single eBook file.

    Examples:
        book-tool validate file ./book.epub
        book-tool validate file ./suspicious.mobi --details
    """
    config = ctx.obj["config"]
    dry_run = ctx.obj["dry_run"]

    try:
        validator = FileValidator(config.get_config())

        if dry_run:
            console.print(f"[yellow]DRY RUN: Would validate file: {file_path}[/yellow]")
            return

        # Validate single file
        result = validator.validate_file(file_path, use_cache=not no_cache)

        # Display result
        _display_single_file_result(result, details)

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        console.print(f"[red]Validation failed: {e}[/red]")
        ctx.exit(1)


@validate.command()
@click.pass_context
def clear_cache(ctx: click.Context) -> None:
    """Clear the validation cache."""
    config = ctx.obj["config"]

    try:
        validator = FileValidator(config.get_config())
        validator.clear_cache()
        console.print("[green]Validation cache cleared successfully[/green]")

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        console.print(f"[red]Failed to clear cache: {e}[/red]")
        ctx.exit(1)


def _display_validation_results(
    results: List,
    show_details: bool,
    quiet: bool,
) -> None:
    """Display validation results in a formatted table."""
    if not results:
        return

    # Generate summary
    validator = FileValidator({})  # Temporary instance for summary generation
    summary = validator.generate_summary(results)

    # Display summary
    if not quiet:
        _display_summary(summary)

    # Display problematic files
    problem_files = [r for r in results if not r.is_valid]
    if problem_files:
        _display_problem_files(problem_files, show_details, quiet)

    # Display all files if details requested and not quiet
    if show_details and not quiet:
        _display_all_files(results)


def _display_summary(summary: dict) -> None:
    """Display validation summary."""
    total = summary["total_files"]
    valid = summary["valid_files"]
    invalid = summary["invalid_files"]
    mismatches = summary["extension_mismatches"]

    # Create summary panel
    summary_text = Text()
    summary_text.append(f"Total files: {total}\n")

    if valid > 0:
        summary_text.append(f"✓ Valid files: {valid}\n", style="green")

    if invalid > 0:
        summary_text.append(f"✗ Invalid files: {invalid}\n", style="red")

    if mismatches > 0:
        summary_text.append(f"⚠ Extension mismatches: {mismatches}\n", style="yellow")

    # Format distribution
    if summary["format_counts"]:
        summary_text.append("\nFormat distribution:\n", style="cyan")
        for fmt, count in sorted(summary["format_counts"].items()):
            summary_text.append(f"  • {fmt}: {count} files\n")

    console.print(Panel(summary_text, title="Validation Summary", border_style="blue"))


def _display_problem_files(
    problem_files: List,
    show_details: bool,
    quiet: bool,
) -> None:
    """Display problematic files in a table."""
    if not problem_files:
        return

    console.print(f"\n[red]Found {len(problem_files)} problematic files:[/red]")

    # Create table
    table = Table(show_header=True, header_style="bold red")
    table.add_column("Status", style="red", width=12)
    table.add_column("File", style="white")
    if show_details:
        table.add_column("Expected", style="cyan", width=10)
        table.add_column("Detected", style="yellow", width=10)
    table.add_column("Issues", style="red")

    for result in problem_files:
        status_symbols = {
            ValidationStatus.INVALID: "✗ Invalid",
            ValidationStatus.CORRUPTED: "⚠ Corrupted",
            ValidationStatus.EXTENSION_MISMATCH: "⚠ Mismatch",
            ValidationStatus.UNREADABLE: "✗ Unreadable",
            ValidationStatus.UNSUPPORTED_FORMAT: "? Unsupported",
        }

        status = status_symbols.get(result.status, str(result.status.value))
        file_name = result.file_path.name
        issues = "; ".join(result.errors[:2])  # Show first 2 errors

        if show_details:
            expected = result.format_expected or "unknown"
            detected = result.format_detected or "unknown"
            table.add_row(status, file_name, expected, detected, issues)
        else:
            table.add_row(status, file_name, issues)

    console.print(table)


def _display_all_files(results: List) -> None:
    """Display all validation results in a detailed table."""
    console.print(f"\n[cyan]Detailed validation results:[/cyan]")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Status", width=8)
    table.add_column("File", style="white")
    table.add_column("Format", style="cyan", width=10)
    table.add_column("Size", style="blue", width=10)
    table.add_column("Issues", style="yellow")

    for result in results:
        if result.is_valid:
            status = "✓"
            status_style = "green"
        elif result.has_extension_mismatch:
            status = "⚠"
            status_style = "yellow"
        else:
            status = "✗"
            status_style = "red"

        file_name = result.file_path.name
        format_str = result.format_detected or result.format_expected or "unknown"

        # Get file size
        try:
            size_bytes = result.file_path.stat().st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes // 1024}KB"
            else:
                size_str = f"{size_bytes // (1024 * 1024)}MB"
        except:
            size_str = "unknown"

        issues = ""
        if result.errors:
            issues = result.errors[0]
        elif result.warnings:
            issues = f"Warning: {result.warnings[0]}"

        table.add_row(
            Text(status, style=status_style), file_name, format_str, size_str, issues
        )

    console.print(table)


def _display_single_file_result(result, show_details: bool) -> None:
    """Display validation result for a single file."""
    # Status and basic info
    status_symbols = {
        ValidationStatus.VALID: ("✓", "green"),
        ValidationStatus.INVALID: ("✗", "red"),
        ValidationStatus.CORRUPTED: ("⚠", "yellow"),
        ValidationStatus.EXTENSION_MISMATCH: ("⚠", "yellow"),
        ValidationStatus.UNREADABLE: ("✗", "red"),
        ValidationStatus.UNSUPPORTED_FORMAT: ("?", "blue"),
    }

    symbol, color = status_symbols.get(result.status, ("?", "white"))

    console.print(f"\n[{color}]{symbol} {result.file_path.name}[/{color}]")
    console.print(f"Status: [{color}]{result.status.value}[/{color}]")

    if result.format_expected:
        console.print(f"Expected format: [cyan]{result.format_expected}[/cyan]")

    if result.format_detected:
        console.print(f"Detected format: [yellow]{result.format_detected}[/yellow]")

    # Show errors
    if result.errors:
        console.print(f"\n[red]Errors:[/red]")
        for error in result.errors:
            console.print(f"  • {error}")

    # Show warnings
    if result.warnings:
        console.print(f"\n[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  • {warning}")

    # Show details if requested
    if show_details and result.details:
        console.print(f"\n[cyan]Details:[/cyan]")
        for key, value in result.details.items():
            console.print(f"  • {key}: {value}")
