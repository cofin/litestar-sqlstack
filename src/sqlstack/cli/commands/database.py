"""Database management CLI commands.

This module provides CLI commands for:
- Loading database fixtures
- Exporting database tables to fixtures

All commands use the @async_inject decorator for automatic dependency injection.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import rich_click as click
from rich import get_console

from sqlstack.cli._utils import (
    display_available_tables,
    display_export_results,
    display_fixture_list,
    display_fixture_results,
    get_fixtures_dir,
    parse_csv_option,
    resolve_table_order,
)
from sqlstack.utils.cli_tools import async_inject
from sqlstack.utils.fixtures import FixtureExporter, FixtureLoader

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver


@click.command(name="load-fixtures", help="Load application fixture data into the database.")
@click.option("--tables", "-t", help="Comma-separated list of specific tables to load (loads all if not specified)")  # pyright: ignore
@click.option("--list", "list_fixtures", is_flag=True, help="List available fixture files")  # pyright: ignore
@async_inject
async def load_fixtures_cmd(driver: AsyncpgDriver, tables: str | None, list_fixtures: bool) -> None:
    """Load application fixture data into the database."""
    if list_fixtures:
        await display_fixture_list()
        return

    console = get_console()
    console.rule("[bold blue]Loading Database Fixtures", style="blue", align="left")
    console.print()

    table_list = parse_csv_option(tables)
    if table_list:
        console.print(f"[dim]loading tables: {', '.join(table_list)}[/dim]")
    else:
        console.print("[dim]loading all available fixtures[/dim]")
    console.print()

    try:
        fixtures_dir = get_fixtures_dir()
        table_order = await resolve_table_order(fixtures_dir)
        loader = FixtureLoader(fixtures_dir, driver, table_order=table_order)
        with console.status("[bold yellow]loading fixtures...", spinner="dots"):
            results = await loader.load_all_fixtures(table_list)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]failed to load fixtures: {exc!s}[/red]")
        return

    if not results:
        console.print("[yellow]no fixture files found to load[/yellow]")
        return

    display_fixture_results(results)


@click.command(name="export-fixtures", help="Export database tables to fixture JSON files.")
@click.option("--tables", "-t", help="Comma-separated list of specific tables to export (exports all if not specified)")  # pyright: ignore
@click.option("--output-dir", "-o", help="Custom output directory (defaults to configured fixtures directory)")  # pyright: ignore
@click.option("--no-compress", is_flag=True, help="Export uncompressed JSON (default is gzipped)")  # pyright: ignore
@click.option("--list", "list_tables", is_flag=True, help="List available tables for export")  # pyright: ignore
@async_inject
async def export_fixtures_cmd(
    driver: AsyncpgDriver, tables: str | None, output_dir: str | None, no_compress: bool, list_tables: bool
) -> None:
    """Export database tables to fixture JSON files."""
    if list_tables:
        await display_available_tables()
        return

    console = get_console()
    console.rule("[bold blue]Exporting Database Fixtures", style="blue", align="left")
    console.print()

    table_list = parse_csv_option(tables)
    if table_list:
        console.print(f"[dim]exporting tables: {', '.join(table_list)}[/dim]")
    else:
        console.print("[dim]exporting all available tables[/dim]")

    output_path = Path(output_dir).expanduser().resolve() if output_dir else None
    if output_path:
        console.print(f"[dim]output directory: {output_path}[/dim]")

    compress = not no_compress
    console.print(f"[dim]compression: {'enabled' if compress else 'disabled'}[/dim]")
    console.print()

    try:
        fixtures_dir = get_fixtures_dir()
        table_order = await resolve_table_order(fixtures_dir)
        exporter = FixtureExporter(fixtures_dir, driver, table_order=table_order)
        with console.status("[bold yellow]exporting fixtures...", spinner="dots"):
            results = await exporter.export_all_fixtures(table_list, output_path, compress)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]failed to export fixtures: {exc!s}[/red]")
        return

    if not results:
        console.print("[yellow]no tables exported[/yellow]")
        return

    display_export_results(results)


# Command list for registration with database_group
database_commands = [load_fixtures_cmd, export_fixtures_cmd]
