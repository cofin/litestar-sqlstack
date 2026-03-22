"""System management commands."""

import logging
import sys
from pathlib import Path
from typing import Any

import rich_click as click
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sqlstack.cli.config import console, left_aligned_rule
from sqlstack.cli.utils import async_inject
from sqlstack.lib.exceptions import ConfigurationError
from sqlstack.lib.settings import get_settings


@click.group(
    name="manage",
    help="[bold green]SQLStack system administration and configuration[/bold green]\n\n"
    "Core system administration tasks including configuration, "
    "database connectivity, and system monitoring.",
)
def manage_group() -> None:
    """System management commands."""


@manage_group.command(name="init", help="Initialize SQLStack system configuration")
def init_system() -> None:
    """Initialize SQLStack system configuration."""
    left_aligned_rule("[bold blue]Initializing SQLStack System", style="blue")
    console.print()

    settings = get_settings()

    with console.status("[bold yellow]Initializing configuration...", spinner="dots"):
        settings.ensure_directories()

    console.print("[green]✓[/green] Successfully initialized SQLStack system")
    console.print()


@manage_group.command(name="status", help="Show system status and backend database connectivity")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed system information")
@async_inject
async def show_status(verbose: bool) -> None:
    """Show system status and backend database connectivity."""
    from sqlstack.config import db, db_manager
    from sqlstack.__metadata__ import __version__

    left_aligned_rule("[bold blue]SQLStack System Status", style="blue")
    console.print()

    try:
        settings = get_settings()
    except ConfigurationError as e:
        console.print(f"\n[red]✗[/red] Configuration error: [red]{e}[/red]")
        console.print()
        raise click.ClickException(str(e)) from e

    header = Text()
    header.append("SQLStack Reference Architecture ", style="bold")
    header.append(f"v{__version__}", style="cyan")
    console.print(Panel(header, border_style="blue", padding=(0, 2)))
    console.print()

    sys_table = Table(title="[bold]System Configuration[/bold]", show_header=False, box=None, padding=(0, 2))
    sys_table.add_column("Setting", style="dim", width=25)
    sys_table.add_column("Value")

    sys_table.add_row(
        "Debug Mode",
        f"[{'green' if settings.app.DEBUG else 'yellow'}]{'Enabled' if settings.app.DEBUG else 'Disabled'}[/]",
    )

    if settings.gcp.PROJECT_ID:
        sys_table.add_row("GCP Project", f"[cyan]{settings.gcp.PROJECT_ID}[/cyan]")

    console.print(sys_table)
    console.print()

    console.print("[bold]Database Connectivity[/bold]")
    console.print()

    with console.status("[yellow]Checking main database...", spinner="dots"):
        try:
            async with db_manager.provide_session(db) as driver:
                result = await driver.select_one("SELECT 1 as ping")
                main_status = "[green]✓ Connected[/green]" if result else "[red]✗ Failed[/red]"
        except Exception as e:
            main_status = f"[red]✗ Error: {str(e)[:50]}[/red]"

    db_table = Table(show_header=False, box=None, padding=(0, 2))
    db_table.add_column("", style="dim", width=25)
    db_table.add_column("")

    db_table.add_row("PostgreSQL (Main)", main_status)

    console.print(db_table)
    console.print()

    if verbose:
        console.print("[bold]Detailed Configuration[/bold]")
        console.print()

        detail_table = Table(show_header=False, box=None, padding=(0, 2))
        detail_table.add_column("Setting", style="dim", width=25)
        detail_table.add_column("Value", style="cyan")

        detail_table.add_row("Log Level", str(settings.log.LEVEL))
        detail_table.add_row("Pool Size", f"{settings.db.POOL_MIN_SIZE}-{settings.db.POOL_MAX_SIZE}")

        console.print(detail_table)
        console.print()


@manage_group.command(name="config", help="Manage configuration settings")
@click.option("--set", "-s", "set_value", nargs=2, type=(str, str), help="Set configuration key-value pair")
@click.option("--get", "-g", help="Get configuration value for key")
@click.option("--list", "-l", "list_config", is_flag=True, help="List all configuration settings")
def manage_config(set_value: tuple[str, str] | None, get: str | None, list_config: bool) -> None:
    """Manage configuration settings."""
    settings = get_settings()

    if set_value:
        left_aligned_rule("[bold blue]Setting Configuration Value", style="blue")
        console.print()

        key, value = set_value

        try:
            with console.status(f"[yellow]Setting {key}...", spinner="dots"):
                settings.set_config_value(key, value)
        except ConfigurationError as e:
            console.print(f"[red]✗[/red] Failed to set configuration: {e}")
            console.print()
            sys.exit(1)

        console.print("[green]✓[/green] Successfully updated configuration")
        console.print(f"  [dim]{key}[/dim] = [cyan]{value}[/cyan]")
        console.print()

    elif get:
        left_aligned_rule("[bold blue]Configuration Value", style="blue")
        console.print()

        try:
            value = settings.get_config_value(get)
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Key", style="dim")
            table.add_column("Value", style="cyan")
            table.add_row(get, str(value))
            console.print(table)
            console.print()
        except ConfigurationError as e:
            console.print(f"[red]✗[/red] Configuration key [yellow]'{get}'[/yellow] not found")
            console.print("[dim]Use --list to see available configuration keys[/dim]")
            console.print()
            raise click.ClickException(str(e)) from e

    elif list_config:
        left_aligned_rule("[bold blue]Configuration Settings", style="blue")
        console.print()

        config_data = settings.list_all_config()
        _display_formatted_config(config_data)

    else:
        console.print("[yellow]ℹ[/yellow]  No action specified")
        console.print("    Use [cyan]--set KEY VALUE[/cyan] to set a configuration value")
        console.print("    Use [cyan]--get KEY[/cyan] to get a configuration value")
        console.print("    Use [cyan]--list[/cyan] to list all configuration settings")
        console.print()


def _format_path_value(value: str | Path) -> str:
    """Format path values for display."""
    if not isinstance(value, (str, Path)):
        return str(value)

    path = Path(value)
    home = Path.home()
    cwd = Path.cwd()

    try:
        rel_to_home = path.relative_to(home)
        return f"~/{rel_to_home}"
    except ValueError:
        pass

    try:
        rel_to_cwd = path.relative_to(cwd)
        return f"./{rel_to_cwd}"
    except ValueError:
        pass

    return str(path)


def _format_config_value(key: str, value: Any) -> str:
    """Format configuration values for display with appropriate styling."""
    if any(sensitive in key.lower() for sensitive in ["password", "secret", "key", "token"]):
        return "[dim italic]***masked***[/dim italic]" if value else "[dim]not set[/dim]"

    if not value:
        return "[dim]not set[/dim]"

    formatted: str
    if isinstance(value, bool):
        color = "green" if value else "yellow"
        display_value = "Yes" if value else "No"
        formatted = f"[{color}]{display_value}[/{color}]"
    elif isinstance(value, list):
        formatted = "[dim]none[/dim]" if not value else f"[cyan]{', '.join(str(item) for item in value)}[/cyan]"
    elif isinstance(value, (int, float)):
        formatted = f"[magenta]{value}[/magenta]"
    elif isinstance(value, (str, Path)) and ("path" in key.lower() or "dir" in key.lower()):
        formatted = f"[cyan]{_format_path_value(value)}[/cyan]"
    elif isinstance(value, str) and value.startswith(("http://", "https://", "postgresql://", "sqlite://")):
        formatted = f"[cyan]{value}[/cyan]"
    else:
        formatted = f"[cyan]{value}[/cyan]"

    return formatted


def _display_formatted_config(config_data: dict[str, dict[str, Any]]) -> None:
    """Display configuration with improved formatting."""
    terminal_width = console.size.width
    table_width = min(terminal_width - 8, 100)

    for i, (section_name, section_config) in enumerate(config_data.items()):
        if i > 0:
            console.print("[dim]" + "─" * table_width + "[/dim]")
            console.print()

        section_text = Text(section_name.title(), style="bold white")
        console.print(section_text)
        console.print()

        table = Table(show_header=False, box=None, padding=(0, 3), width=table_width, min_width=60)

        max_key_length = max(len(key.replace("_", " ").title()) for key in section_config) if section_config else 20
        key_width = min(max_key_length + 4, table_width // 3)

        table.add_column("Setting", style="dim", width=key_width, no_wrap=False)
        table.add_column("Value", no_wrap=False)

        for key in sorted(section_config.keys()):
            value = section_config[key]
            display_key = key.replace("_", " ").title()
            display_value = _format_config_value(key, value)
            table.add_row(display_key, display_value)

        console.print(table)
        console.print()
