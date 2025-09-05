"""
Config command module for Calibre Books CLI.

This module provides commands for managing configuration,
including initialization, validation, and profile management.
"""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.syntax import Syntax

from calibre_books.config.manager import ConfigManager
from calibre_books.config.schema import ConfigurationSchema

console = Console()
logger = logging.getLogger(__name__)


@click.group(name="config")
@click.pass_context
def config(ctx: click.Context) -> None:
    """Manage configuration settings."""
    pass


@config.command()
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Run interactive configuration wizard.",
)
@click.option(
    "--overwrite",
    "-o",
    is_flag=True,
    help="Overwrite existing configuration.",
)
@click.option(
    "--minimal",
    "-m",
    is_flag=True,
    help="Create minimal configuration with defaults.",
)
@click.pass_context
def init(
    ctx: click.Context,
    interactive: bool,
    overwrite: bool,
    minimal: bool,
) -> None:
    """
    Initialize configuration file with setup wizard.
    
    Examples:
        calibre-books config init --interactive
        calibre-books config init --minimal
        calibre-books config init --overwrite
    """
    dry_run = ctx.obj["dry_run"]
    
    try:
        config_manager = ConfigManager()
        config_path = config_manager.get_config_path()
        
        # Check if config already exists
        if config_path.exists() and not overwrite:
            console.print(f"[yellow]Configuration already exists at: {config_path}[/yellow]")
            if not Confirm.ask("Do you want to overwrite it?"):
                console.print("Configuration initialization cancelled.")
                return
        
        if dry_run:
            console.print("[yellow]DRY RUN: Would initialize configuration:[/yellow]")
            console.print(f"  Config file: {config_path}")
            console.print(f"  Interactive: {interactive}")
            console.print(f"  Minimal: {minimal}")
            console.print(f"  Overwrite: {overwrite}")
            return
        
        if interactive:
            # Interactive configuration wizard
            console.print("[bold blue]Calibre Books Configuration Wizard[/bold blue]")
            console.print("This wizard will help you set up calibre-books for your system.\n")
            
            config_data = {}
            
            # Download settings
            console.print("[bold]Download Settings[/bold]")
            config_data["download"] = {
                "default_format": Prompt.ask(
                    "Preferred download format",
                    choices=["mobi", "epub", "pdf", "azw3"],
                    default="mobi"
                ),
                "download_path": Prompt.ask(
                    "Download directory",
                    default="~/Downloads/Books"
                ),
                "librarian_path": Prompt.ask(
                    "Librarian CLI path",
                    default="librarian"
                ),
            }
            
            # Calibre settings
            console.print("\n[bold]Calibre Settings[/bold]")
            config_data["calibre"] = {
                "library_path": Prompt.ask(
                    "Default Calibre library path",
                    default="~/Calibre-Library"
                ),
                "cli_path": Prompt.ask(
                    "Calibre CLI tools path (or 'auto' for auto-detection)",
                    default="auto"
                ),
            }
            
            # ASIN lookup settings
            console.print("\n[bold]ASIN Lookup Settings[/bold]")
            cache_path = Prompt.ask(
                "ASIN cache directory",
                default="~/.calibre-books/cache"
            )
            
            sources = []
            if Confirm.ask("Enable Amazon ASIN lookup?", default=True):
                sources.append("amazon")
            if Confirm.ask("Enable Goodreads ASIN lookup?", default=True):
                sources.append("goodreads")
            if Confirm.ask("Enable OpenLibrary ASIN lookup?", default=True):
                sources.append("openlibrary")
            
            config_data["asin_lookup"] = {
                "cache_path": f"{cache_path}/asin_cache.json",
                "sources": sources,
                "rate_limit": 2.0,
            }
            
            # Conversion settings
            console.print("\n[bold]Conversion Settings[/bold]")
            config_data["conversion"] = {
                "max_parallel": int(Prompt.ask(
                    "Maximum parallel conversion processes",
                    default="4"
                )),
                "output_path": Prompt.ask(
                    "Conversion output directory",
                    default="~/Converted-Books"
                ),
                "kfx_plugin_required": Confirm.ask(
                    "Require KFX plugin for conversions?",
                    default=True
                ),
            }
            
            # Logging settings
            console.print("\n[bold]Logging Settings[/bold]")
            config_data["logging"] = {
                "level": Prompt.ask(
                    "Default log level",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    default="INFO"
                ),
                "file": f"{cache_path}/logs/calibre-books.log",
                "format": Prompt.ask(
                    "Log format",
                    choices=["simple", "detailed"],
                    default="detailed"
                ),
            }
            
        else:
            # Use default configuration
            config_data = ConfigurationSchema.get_default_config()
        
        # Create configuration
        config_manager.create_config(config_data, minimal=minimal)
        
        console.print(f"[green]Configuration initialized successfully![/green]")
        console.print(f"Config file: {config_path}")
        console.print("\nYou can modify settings using:")
        console.print("  calibre-books config edit")
        console.print("  calibre-books config show")
        
    except Exception as e:
        logger.error(f"Configuration initialization failed: {e}")
        console.print(f"[red]Configuration initialization failed: {e}[/red]")
        ctx.exit(1)


@config.command()
@click.option(
    "--section",
    "-s",
    help="Show only specific configuration section.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["yaml", "json", "table"]),
    default="table",
    help="Output format.",
)
@click.pass_context
def show(
    ctx: click.Context,
    section: Optional[str],
    format: str,
) -> None:
    """
    Display current configuration.
    
    Examples:
        calibre-books config show
        calibre-books config show --section download
        calibre-books config show --format yaml
    """
    try:
        config_manager = ConfigManager()
        config_data = config_manager.get_config()
        
        if section:
            if section not in config_data:
                console.print(f"[red]Section '{section}' not found in configuration[/red]")
                ctx.exit(1)
            config_data = {section: config_data[section]}
        
        if format == "yaml":
            yaml_content = config_manager.to_yaml(config_data)
            syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
            console.print(syntax)
            
        elif format == "json":
            json_content = config_manager.to_json(config_data)
            syntax = Syntax(json_content, "json", theme="monokai", line_numbers=True)
            console.print(syntax)
            
        elif format == "table":
            for section_name, section_data in config_data.items():
                table = Table(title=f"Configuration: {section_name}")
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="white")
                
                for key, value in section_data.items():
                    # Format complex values
                    if isinstance(value, list):
                        value_str = ", ".join(str(v) for v in value)
                    elif isinstance(value, dict):
                        value_str = "{ ... }"  # Nested dict
                    else:
                        value_str = str(value)
                    
                    table.add_row(key, value_str)
                
                console.print(table)
        
    except Exception as e:
        logger.error(f"Failed to show configuration: {e}")
        console.print(f"[red]Failed to show configuration: {e}[/red]")
        ctx.exit(1)


@config.command()
@click.option(
    "--editor",
    "-e",
    help="Editor to use (default: system default).",
)
@click.pass_context
def edit(
    ctx: click.Context,
    editor: Optional[str],
) -> None:
    """
    Edit configuration file in your preferred editor.
    
    Examples:
        calibre-books config edit
        calibre-books config edit --editor vim
    """
    import subprocess
    import os
    
    try:
        config_manager = ConfigManager()
        config_path = config_manager.get_config_path()
        
        if not config_path.exists():
            console.print("[red]No configuration file found. Run 'calibre-books config init' first.[/red]")
            ctx.exit(1)
        
        # Determine editor
        if not editor:
            editor = os.environ.get("EDITOR", "nano")
        
        console.print(f"Opening configuration file with {editor}...")
        console.print(f"File: {config_path}")
        
        # Open editor
        try:
            subprocess.run([editor, str(config_path)], check=True)
        except subprocess.CalledProcessError:
            console.print(f"[red]Failed to open editor: {editor}[/red]")
            ctx.exit(1)
        except FileNotFoundError:
            console.print(f"[red]Editor not found: {editor}[/red]")
            console.print("Try specifying a different editor with --editor")
            ctx.exit(1)
        
        # Validate configuration after editing
        try:
            config_manager.load_config()
            console.print("[green]Configuration updated successfully![/green]")
        except Exception as e:
            console.print(f"[red]Configuration validation failed: {e}[/red]")
            console.print("Please fix the configuration file before using calibre-books.")
            ctx.exit(1)
        
    except Exception as e:
        logger.error(f"Failed to edit configuration: {e}")
        console.print(f"[red]Failed to edit configuration: {e}[/red]")
        ctx.exit(1)


@config.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """
    Validate configuration file and check dependencies.
    
    Examples:
        calibre-books config validate
    """
    try:
        config_manager = ConfigManager()
        
        console.print("Validating configuration...")
        
        # Load and validate config
        try:
            config_data = config_manager.get_config()
            console.print("[green]✓ Configuration file is valid[/green]")
        except Exception as e:
            console.print(f"[red]✗ Configuration validation failed: {e}[/red]")
            ctx.exit(1)
        
        # Check dependencies
        console.print("\nChecking dependencies...")
        
        dependency_checks = config_manager.check_dependencies()
        
        for check in dependency_checks:
            status = "[green]✓[/green]" if check.available else "[red]✗[/red]"
            console.print(f"{status} {check.name}: {check.status}")
            
            if not check.available and check.install_hint:
                console.print(f"   Hint: {check.install_hint}")
        
        # Check paths
        console.print("\nChecking configured paths...")
        
        path_checks = config_manager.check_paths()
        
        for check in path_checks:
            if check.exists:
                console.print(f"[green]✓[/green] {check.name}: {check.path}")
            else:
                console.print(f"[yellow]![/yellow] {check.name}: {check.path} (will be created)")
        
        # Overall status
        all_deps_ok = all(check.available for check in dependency_checks)
        
        if all_deps_ok:
            console.print("\n[green]All checks passed! calibre-books is ready to use.[/green]")
        else:
            console.print("\n[yellow]Some dependencies are missing. calibre-books may not work correctly.[/yellow]")
            console.print("Please install the missing dependencies and run validation again.")
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        console.print(f"[red]Configuration validation failed: {e}[/red]")
        ctx.exit(1)


@config.command()
@click.option(
    "--name",
    "-n",
    required=True,
    help="Profile name.",
)
@click.option(
    "--from-current",
    "-c",
    is_flag=True,
    help="Create profile from current configuration.",
)
@click.pass_context
def create_profile(
    ctx: click.Context,
    name: str,
    from_current: bool,
) -> None:
    """
    Create a new configuration profile.
    
    Examples:
        calibre-books config create-profile --name work
        calibre-books config create-profile --name home --from-current
    """
    dry_run = ctx.obj["dry_run"]
    
    try:
        config_manager = ConfigManager()
        
        if dry_run:
            console.print(f"[yellow]DRY RUN: Would create profile '{name}'[/yellow]")
            console.print(f"  From current config: {from_current}")
            return
        
        config_manager.create_profile(name, from_current=from_current)
        
        console.print(f"[green]Profile '{name}' created successfully![/green]")
        console.print(f"Switch to it with: calibre-books config use-profile --name {name}")
        
    except Exception as e:
        logger.error(f"Failed to create profile: {e}")
        console.print(f"[red]Failed to create profile: {e}[/red]")
        ctx.exit(1)


@config.command()
@click.option(
    "--name",
    "-n",
    required=True,
    help="Profile name to use.",
)
@click.pass_context
def use_profile(
    ctx: click.Context,
    name: str,
) -> None:
    """
    Switch to a different configuration profile.
    
    Examples:
        calibre-books config use-profile --name work
        calibre-books config use-profile --name default
    """
    dry_run = ctx.obj["dry_run"]
    
    try:
        config_manager = ConfigManager()
        
        if dry_run:
            console.print(f"[yellow]DRY RUN: Would switch to profile '{name}'[/yellow]")
            return
        
        config_manager.use_profile(name)
        
        console.print(f"[green]Switched to profile '{name}'[/green]")
        
    except Exception as e:
        logger.error(f"Failed to switch profile: {e}")
        console.print(f"[red]Failed to switch profile: {e}[/red]")
        ctx.exit(1)


@config.command()
@click.pass_context
def list_profiles(ctx: click.Context) -> None:
    """List all available configuration profiles."""
    try:
        config_manager = ConfigManager()
        profiles = config_manager.list_profiles()
        current_profile = config_manager.get_current_profile()
        
        if not profiles:
            console.print("[yellow]No profiles found[/yellow]")
            return
        
        table = Table(title="Configuration Profiles")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Created", style="dim")
        
        for profile in profiles:
            status = "[green]current[/green]" if profile.name == current_profile else ""
            table.add_row(
                profile.name,
                status,
                profile.created.isoformat(),
            )
        
        console.print(table)
        
    except Exception as e:
        logger.error(f"Failed to list profiles: {e}")
        console.print(f"[red]Failed to list profiles: {e}[/red]")
        ctx.exit(1)