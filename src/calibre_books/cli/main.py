#!/usr/bin/env python3
"""
Main CLI entry point for Calibre Books tool.

This module provides the main command dispatcher and global options for the
book-tool CLI tool.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from .. import __version__
from ..config.manager import ConfigManager
from ..utils.logging import setup_logging

# Import command modules
from .process import process
from .asin import asin
from .convert import convert
from .config import config as config_cmd
from .library import library

console = Console()


def version_option(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Show version information and exit."""
    if not value or ctx.resilient_parsing:
        return
    console.print(f"book-tool version {__version__}")
    ctx.exit()


@click.group(invoke_without_command=True)
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=version_option,
    help="Show version information and exit.",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file.",
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Set logging level.",
)
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Show what would be done without making changes.",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (can be used multiple times).",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Suppress non-error output.",
)
@click.pass_context
def main(
    ctx: click.Context,
    config: Optional[Path],
    log_level: str,
    dry_run: bool,
    verbose: int,
    quiet: bool,
) -> None:
    """
    Book Tool - Professional eBook processing, ASIN lookup, and KFX conversion.
    
    A comprehensive command-line interface for processing existing eBook files,
    adding ASIN metadata, and converting to KFX format for Goodreads integration.
    
    Examples:
        book-tool process scan --input-dir ./books --check-asin
        book-tool process prepare --input-dir ./books --add-asin --lookup
        book-tool convert kfx --input-dir ./books --parallel 4
        book-tool config init --interactive
    """
    # Set up context object to pass configuration between commands
    ctx.ensure_object(dict)
    
    # Adjust log level based on verbosity
    if quiet:
        log_level = "ERROR"
    elif verbose >= 2:
        log_level = "DEBUG"
    elif verbose >= 1:
        log_level = "INFO"
    
    # Set up logging
    setup_logging(log_level, quiet=quiet)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize configuration manager
        config_manager = ConfigManager(config_path=config)
        ctx.obj["config"] = config_manager
        ctx.obj["dry_run"] = dry_run
        ctx.obj["verbose"] = verbose
        ctx.obj["quiet"] = quiet
        
        logger.debug(f"CLI initialized with config: {config}, dry_run: {dry_run}")
        
        # If no command specified, show help
        if ctx.invoked_subcommand is None:
            console.print("[bold blue]Book Tool[/bold blue]")
            console.print(f"Version: {__version__}")
            console.print("\nUse --help for more information or specify a command:")
            console.print("  • [bold]process[/bold] - Process existing eBook files")
            console.print("  • [bold]asin[/bold] - Manage ASINs and metadata")
            console.print("  • [bold]convert[/bold] - Convert book formats")
            console.print("  • [bold]library[/bold] - Manage Calibre library")
            console.print("  • [bold]config[/bold] - Configuration management")
            console.print("\nExample: book-tool process scan -i ./books")
            
    except Exception as e:
        logger.error(f"Failed to initialize CLI: {e}")
        if verbose >= 1:
            logger.exception("Full error details:")
        console.print(f"[bold red]Error:[/bold red] {e}")
        ctx.exit(1)


# Add command groups
main.add_command(process)
main.add_command(asin)
main.add_command(convert)
main.add_command(library)
main.add_command(config_cmd)


def cli_entry_point() -> None:
    """Entry point for the CLI when installed as a package."""
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_entry_point()