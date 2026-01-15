"""CLI utility functions for fixture operations and console display."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from anyio import Path as AsyncPath
from rich import get_console
from rich.table import Table

from sqlstack.lib.settings import BASE_DIR
from sqlstack.utils.fixtures import FixtureProcessor

ConsoleResult = dict[str, dict[str, Any] | str]
ExportResults = dict[str, str]

_KILOBYTE = 1024
_MEGABYTE = 1024 * 1024


def get_fixtures_dir() -> Path:
    """Get the default fixtures directory path."""
    return BASE_DIR / "db" / "fixtures"


def parse_csv_option(value: str | None) -> list[str] | None:
    """Parse a comma-separated string into a list of stripped values."""
    if value is None:
        return None
    tables = [item.strip() for item in value.split(",") if item.strip()]
    return tables or None


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes >= _MEGABYTE:
        return f"{size_bytes / _MEGABYTE:.1f} MB"
    if size_bytes >= _KILOBYTE:
        return f"{size_bytes / _KILOBYTE:.1f} KB"
    return f"{size_bytes} B"


async def resolve_table_order(fixtures_dir: Path) -> list[str]:
    """Resolve table load order from fixture files in directory."""
    processor = FixtureProcessor(fixtures_dir)
    async_dir = AsyncPath(fixtures_dir)
    json_files = [p async for p in async_dir.glob("*.json")]
    gzip_files = [p async for p in async_dir.glob("*.json.gz")]
    files = sorted(json_files + gzip_files, key=lambda p: p.name)
    table_names: list[str] = []
    for fixture_file in files:
        table_name = processor.get_table_name(fixture_file.name)
        if table_name not in table_names:
            table_names.append(table_name)
    return table_names


async def display_fixture_list() -> None:
    """Display available fixture files in a formatted table."""
    console = get_console()
    console.rule("[bold blue]Available Fixture Files", style="blue", align="left")
    console.print()

    fixtures_dir = get_fixtures_dir()
    async_dir = AsyncPath(fixtures_dir)
    if not await async_dir.exists():
        console.print(f"[yellow]fixtures directory not found: {fixtures_dir}[/yellow]")
        return

    processor = FixtureProcessor(fixtures_dir)
    json_files = [p async for p in async_dir.glob("*.json")]
    gzip_files = [p async for p in async_dir.glob("*.json.gz")]
    fixture_files = sorted(json_files + gzip_files, key=lambda p: p.name)

    if not fixture_files:
        console.print("[yellow]no fixture files found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold blue", expand=True)
    table.add_column("table", style="cyan", ratio=2)
    table.add_column("file", style="dim", ratio=3)
    table.add_column("records", justify="right", ratio=1)
    table.add_column("size", justify="right", ratio=1)
    table.add_column("status", ratio=2)

    for fixture_file in fixture_files:
        table_name = processor.get_table_name(fixture_file.name)
        try:
            data = processor.load_fixture_data(Path(fixture_file))
            record_count = len(data)
            status = "[green]ready[/green]" if record_count else "[yellow]empty[/yellow]"
        except Exception as exc:  # noqa: BLE001
            record_count = 0
            status = f"[red]error: {exc!s}[/red]"

        stat_result = await fixture_file.stat()
        size_bytes = stat_result.st_size
        table.add_row(table_name, fixture_file.name, str(record_count), format_size(size_bytes), status)

    console.print(table)
    console.print()


def get_fixture_status(upserted: int, failed: int) -> str:
    """Get formatted status string for fixture load results."""
    if upserted and not failed:
        return f"[green]loaded {upserted}[/green]"
    if upserted and failed:
        return f"[yellow]partial: {upserted} ok, {failed} failed[/yellow]"
    if failed:
        return f"[red]failed {failed}[/red]"
    return "[dim]no records[/dim]"


def display_fixture_results(results: ConsoleResult) -> None:
    """Display fixture load results in a formatted table."""
    console = get_console()
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("table", style="cyan", ratio=2)
    table.add_column("upserted", justify="right")
    table.add_column("failed", justify="right")
    table.add_column("records", justify="right")
    table.add_column("status", ratio=2)

    total_upserted = 0
    total_failed = 0
    total_records = 0

    for table_name, result in results.items():
        if isinstance(result, dict):
            upserted = int(result.get("upserted", 0) or 0)
            failed = int(result.get("failed", 0) or 0)
            total = int(result.get("total", 0) or 0)
            status = get_fixture_status(upserted, failed)
        else:
            upserted = failed = total = 0
            status = f"[red]{result}[/red]"

        total_upserted += upserted
        total_failed += failed
        total_records += total

        table.add_row(table_name, str(upserted), str(failed), str(total), status)

    console.print(table)
    console.print()

    console.print("[bold]Summary:[/bold]")
    console.print(f"  [green]upserted: {total_upserted}[/green]")
    if total_failed > 0:
        console.print(f"  [red]failed: {total_failed}[/red]")
    console.print(f"  [dim]fixtures contained: {total_records} records[/dim]")
    console.print()


def display_export_results(results: ExportResults) -> None:
    """Display fixture export results in a formatted table."""
    console = get_console()
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("table", style="cyan", ratio=2)
    table.add_column("output", style="dim", ratio=4)
    table.add_column("status", ratio=2)

    total_success = 0
    total_failed = 0

    for table_name, result in results.items():
        if result.startswith("/") or result.endswith((".json", ".json.gz")):
            status = "[green]exported[/green]"
            file_display = result
            total_success += 1
        else:
            status = f"[red]{result}[/red]"
            file_display = "[dim]n/a[/dim]"
            total_failed += 1

        table.add_row(table_name, file_display, status)

    console.print(table)
    console.print()

    console.print("[bold]Summary:[/bold]")
    console.print(f"  [green]exported: {total_success} tables[/green]")
    if total_failed > 0:
        console.print(f"  [red]failed: {total_failed} tables[/red]")
    console.print()


async def display_available_tables() -> None:
    """Display available tables for export in a formatted table."""
    console = get_console()
    console.rule("[bold blue]Available Tables for Export", style="blue", align="left")
    console.print()

    fixtures_dir = get_fixtures_dir()
    async_dir = AsyncPath(fixtures_dir)
    if not await async_dir.exists():
        console.print(f"[yellow]fixtures directory not found: {fixtures_dir}[/yellow]")
        return

    table_order = await resolve_table_order(fixtures_dir)
    if not table_order:
        console.print("[yellow]no tables discovered in fixtures directory[/yellow]")
        return

    table = Table(show_header=True, header_style="bold blue", expand=True)
    table.add_column("table", style="cyan", ratio=2)
    table.add_column("load order", justify="center")

    for index, table_name in enumerate(table_order, start=1):
        table.add_row(table_name, str(index))

    console.print(table)
    console.print(f"[dim]default output directory: {fixtures_dir}[/dim]")
    console.print(f"[dim]total tables: {len(table_order)}[/dim]")
    console.print()


__all__ = (
    "ConsoleResult",
    "ExportResults",
    "display_available_tables",
    "display_export_results",
    "display_fixture_list",
    "display_fixture_results",
    "format_size",
    "get_fixture_status",
    "get_fixtures_dir",
    "parse_csv_option",
    "resolve_table_order",
)
