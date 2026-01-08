from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import rich_click as click
from rich import get_console
from rich.table import Table
from sqlspec import sql
from sqlspec.utils.sync_tools import run_
from sqlspec.utils.text import slugify

from sqlstack.config import DEFAULT_ACCESS_ROLE, SUPERUSER_ACCESS_ROLE, db
from sqlstack.domain.accounts.schemas import UserCreate
from sqlstack.domain.accounts.services import UserRoleService, UserService
from sqlstack.lib.settings import BASE_DIR
from sqlstack.utils.fixtures import FixtureExporter, FixtureLoader, FixtureProcessor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlspec.driver import AsyncDriverAdapterBase

ConsoleResult = dict[str, dict[str, Any] | str]
ExportResults = dict[str, str]

DEFAULT_ROLE_SLUG = slugify(DEFAULT_ACCESS_ROLE)
SUPERUSER_ROLE_SLUG = slugify(SUPERUSER_ACCESS_ROLE)
_KILOBYTE = 1024
_MEGABYTE = 1024 * 1024


@asynccontextmanager
async def _provide_driver() -> AsyncIterator[AsyncDriverAdapterBase]:
    async with db.provide_session() as driver:
        yield driver


def _get_fixtures_dir() -> Path:
    return BASE_DIR / "db" / "fixtures"


def _parse_csv_option(value: str | None) -> list[str] | None:
    if value is None:
        return None
    tables = [item.strip() for item in value.split(",") if item.strip()]
    return tables or None


def _resolve_table_order(fixtures_dir: Path) -> list[str]:
    processor = FixtureProcessor(fixtures_dir)
    files = sorted(list(fixtures_dir.glob("*.json")) + list(fixtures_dir.glob("*.json.gz")))
    table_names: list[str] = []
    for fixture_file in files:
        table_name = processor.get_table_name(fixture_file.name)
        if table_name not in table_names:
            table_names.append(table_name)
    return table_names


def _format_size(size_bytes: int) -> str:
    if size_bytes >= _MEGABYTE:
        return f"{size_bytes / _MEGABYTE:.1f} MB"
    if size_bytes >= _KILOBYTE:
        return f"{size_bytes / _KILOBYTE:.1f} KB"
    return f"{size_bytes} B"


def _display_fixture_list() -> None:
    console = get_console()
    console.rule("[bold blue]Available Fixture Files", style="blue", align="left")
    console.print()

    fixtures_dir = _get_fixtures_dir()
    if not fixtures_dir.exists():
        console.print(f"[yellow]fixtures directory not found: {fixtures_dir}[/yellow]")
        return

    processor = FixtureProcessor(fixtures_dir)
    fixture_files = sorted(list(fixtures_dir.glob("*.json")) + list(fixtures_dir.glob("*.json.gz")))

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
            data = processor.load_fixture_data(fixture_file)
            record_count = len(data)
            status = "[green]ready[/green]" if record_count else "[yellow]empty[/yellow]"
        except Exception as exc:  # noqa: BLE001
            record_count = 0
            status = f"[red]error: {exc!s}[/red]"

        size_bytes = fixture_file.stat().st_size
        table.add_row(table_name, fixture_file.name, str(record_count), _format_size(size_bytes), status)

    console.print(table)
    console.print()


def _display_fixture_results(results: ConsoleResult) -> None:
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
            status = _get_fixture_status(upserted, failed)
        else:
            upserted = failed = total = 0
            status = f"[red]{result}[/red]"

        total_upserted += upserted
        total_failed += failed
        total_records += total

        table.add_row(table_name, str(upserted), str(failed), str(total), status)

    console.print(table)
    console.print()
    _print_fixture_summary(total_upserted, total_failed, total_records)


def _get_fixture_status(upserted: int, failed: int) -> str:
    if upserted and not failed:
        return f"[green]loaded {upserted}[/green]"
    if upserted and failed:
        return f"[yellow]partial: {upserted} ok, {failed} failed[/yellow]"
    if failed:
        return f"[red]failed {failed}[/red]"
    return "[dim]no records[/dim]"


def _print_fixture_summary(total_upserted: int, total_failed: int, total_records: int) -> None:
    console = get_console()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  • [green]upserted: {total_upserted}[/green]")
    if total_failed > 0:
        console.print(f"  • [red]failed: {total_failed}[/red]")
    console.print(f"  • [dim]fixtures contained: {total_records} records[/dim]")
    console.print()


def _display_export_results(results: ExportResults) -> None:
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
    _print_export_summary(total_success, total_failed)


def _print_export_summary(total_success: int, total_failed: int) -> None:
    console = get_console()
    console.print("[bold]Summary:[/bold]")
    console.print(f"  • [green]exported: {total_success} tables[/green]")
    if total_failed > 0:
        console.print(f"  • [red]failed: {total_failed} tables[/red]")
    console.print()


async def _ensure_role(
    driver: AsyncDriverAdapterBase, *, name: str, slug: str, description: str | None = None
) -> tuple[UUID, bool]:
    existing = await driver.select_one_or_none(sql.select("id").from_("role").where_eq("slug", slug))
    if existing:
        return cast("UUID", existing["id"]), False

    result = await driver.select_one(
        sql.insert("role")
        .values(
            id=uuid4(),
            name=name,
            slug=slug,
            description=description,
            created_at=sql.raw("NOW()"),
            updated_at=sql.raw("NOW()"),
        )
        .returning("id")
    )
    return cast("UUID", result["id"]), True


async def _ensure_user_role_assignment(
    service: UserRoleService, *, user_id: UUID, role_id: UUID, role_slug: str
) -> bool:
    if await service.user_has_role_by_slug(user_id, role_slug):
        return False
    await service.assign_role_to_user(user_id, role_id)
    return True


@click.command(name="load-fixtures", help="Load application fixture data into the database.")
@click.option("--tables", "-t", help="Comma-separated list of specific tables to load (loads all if not specified)")  # pyright: ignore
@click.option("--list", "list_fixtures", is_flag=True, help="List available fixture files")  # pyright: ignore
def load_fixtures_cmd(tables: str | None, list_fixtures: bool) -> None:
    """Load application fixture data into the database."""

    if list_fixtures:
        _display_fixture_list()
        return

    _load_fixture_data(tables)


def _load_fixture_data(tables: str | None) -> None:
    """Load fixture data into database."""
    console = get_console()
    console.rule("[bold blue]Loading Database Fixtures", style="blue", align="left")
    console.print()

    table_list = _parse_csv_option(tables)
    if table_list:
        console.print(f"[dim]loading tables: {', '.join(table_list)}[/dim]")
    else:
        console.print("[dim]loading all available fixtures[/dim]")
    console.print()

    async def _load() -> ConsoleResult:
        fixtures_dir = _get_fixtures_dir()
        table_order = _resolve_table_order(fixtures_dir)
        async with _provide_driver() as driver:
            loader = FixtureLoader(fixtures_dir, driver, table_order=table_order)
            with console.status("[bold yellow]loading fixtures...", spinner="dots"):
                return await loader.load_all_fixtures(table_list)

    try:
        results = run_(_load)()
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]failed to load fixtures: {exc!s}[/red]")
        return

    if not results:
        console.print("[yellow]no fixture files found to load[/yellow]")
        return

    _display_fixture_results(results)


@click.command(name="export-fixtures", help="Export database tables to fixture JSON files.")
@click.option("--tables", "-t", help="Comma-separated list of specific tables to export (exports all if not specified)")  # pyright: ignore
@click.option("--output-dir", "-o", help="Custom output directory (defaults to configured fixtures directory)")  # pyright: ignore
@click.option("--no-compress", is_flag=True, help="Export uncompressed JSON (default is gzipped)")  # pyright: ignore
@click.option("--list", "list_tables", is_flag=True, help="List available tables for export")  # pyright: ignore
def export_fixtures_cmd(tables: str | None, output_dir: str | None, no_compress: bool, list_tables: bool) -> None:
    """Export database tables to fixture JSON files."""

    if list_tables:
        _display_available_tables()
        return

    _export_fixture_data(tables, output_dir, no_compress)


def _display_available_tables() -> None:
    console = get_console()
    console.rule("[bold blue]Available Tables for Export", style="blue", align="left")
    console.print()

    fixtures_dir = _get_fixtures_dir()
    if not fixtures_dir.exists():
        console.print(f"[yellow]fixtures directory not found: {fixtures_dir}[/yellow]")
        return

    table_order = _resolve_table_order(fixtures_dir)
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


def _export_fixture_data(tables: str | None, output_dir: str | None, no_compress: bool) -> None:
    console = get_console()
    console.rule("[bold blue]Exporting Database Fixtures", style="blue", align="left")
    console.print()

    table_list = _parse_csv_option(tables)
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

    async def _export() -> ExportResults:
        fixtures_dir = _get_fixtures_dir()
        table_order = _resolve_table_order(fixtures_dir)
        async with _provide_driver() as driver:
            exporter = FixtureExporter(fixtures_dir, driver, table_order=table_order)
            with console.status("[bold yellow]exporting fixtures...", spinner="dots"):
                return await exporter.export_all_fixtures(table_list, output_path, compress)

    try:
        results = run_(_export)()
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]failed to export fixtures: {exc!s}[/red]")
        return

    if not results:
        console.print("[yellow]no tables exported[/yellow]")
        return

    _display_export_results(results)


@click.group(name="users", invoke_without_command=False, help="Manage application users and roles.")
@click.pass_context  # type: ignore[arg-type]
def user_management_group(_: dict[str, Any]) -> None:
    """Manage application users."""


@user_management_group.command(name="create-user", help="Create a user")
@click.option(  # pyright: ignore
    "--email", help="Email of the new user", type=click.STRING, required=False, show_default=False
)
@click.option(  # pyright: ignore
    "--name", help="Full name of the new user", type=click.STRING, required=False, show_default=False
)
@click.option(  # pyright: ignore
    "--password", help="Password", type=click.STRING, required=False, show_default=False
)
@click.option(  # pyright: ignore
    "--superuser",
    help="Create as a superuser",
    type=click.BOOL,
    default=False,
    required=False,
    show_default=False,
    is_flag=True,
)
def create_user(email: str | None, name: str | None, password: str | None, superuser: bool | None) -> None:
    """Create a user."""
    from typing import cast as typing_cast

    import anyio

    console = get_console()

    async def _create_user(email: str, password: str, name: str | None = None, superuser: bool = False) -> None:
        async with _provide_driver() as driver:
            user_service = UserService(driver)
            role_service = UserRoleService(driver)

            async with user_service.begin_transaction():
                user = await user_service.create_user(
                    UserCreate(
                        email=email,
                        password=password,
                        name=name,
                        is_superuser=superuser,
                        is_active=True,
                        is_verified=superuser,
                    )
                )

                assigned_role = False
                if superuser:
                    role_id, created_role = await _ensure_role(
                        driver, name=SUPERUSER_ACCESS_ROLE, slug=SUPERUSER_ROLE_SLUG
                    )
                    assigned_role = await _ensure_user_role_assignment(
                        role_service, user_id=user.id, role_id=role_id, role_slug=SUPERUSER_ROLE_SLUG
                    )
                    if created_role:
                        console.print(f"[green]created role: {SUPERUSER_ACCESS_ROLE}[/green]")
                    if assigned_role:
                        console.print(f"[green]assigned superuser role to {email}[/green]")

            console.print(f"[green]created user {user.email}[/green]")

    console.rule("Create a new application user.")
    email = email or click.prompt("Email")
    name = name or click.prompt("Full Name", show_default=False)
    password = password or click.prompt("Password", hide_input=True, confirmation_prompt=True)
    superuser = superuser or click.prompt("Create as superuser?", show_default=True, type=click.BOOL)

    anyio.run(
        _create_user, typing_cast("str", email), typing_cast("str", password), name, typing_cast("bool", superuser)
    )


@user_management_group.command(name="promote-to-superuser", help="Promotes a user to application superuser")
@click.option(  # pyright: ignore
    "--email", help="Email of the user", type=click.STRING, required=False, show_default=False
)
def promote_to_superuser(email: str | None) -> None:
    """Promote a user to superuser."""
    from typing import cast as typing_cast

    import anyio

    console = get_console()

    async def _promote_to_superuser(email: str) -> None:
        async with _provide_driver() as driver:
            role_service = UserRoleService(driver)

            user_record = await driver.select_one_or_none(
                sql.select("id", "is_superuser").from_("user_account").where_eq("email", email)
            )
            if user_record is None:
                console.print(f"[red]user {email} not found[/red]")
                return

            user_id = cast("UUID", user_record["id"])
            already_superuser = bool(user_record.get("is_superuser"))

            role_id, created_role = await _ensure_role(driver, name=SUPERUSER_ACCESS_ROLE, slug=SUPERUSER_ROLE_SLUG)
            assigned_role = await _ensure_user_role_assignment(
                role_service, user_id=user_id, role_id=role_id, role_slug=SUPERUSER_ROLE_SLUG
            )

            await driver.execute(
                sql.update("user_account").set(is_superuser=True, updated_at=sql.raw("NOW()")).where_eq("id", user_id)
            )

            if created_role:
                console.print(f"[green]created role: {SUPERUSER_ACCESS_ROLE}[/green]")
            if assigned_role:
                console.print(f"[green]assigned superuser role to {email}[/green]")
            if already_superuser:
                console.print(f"[yellow]{email} was already a superuser[/yellow]")
            else:
                console.print(f"[green]updated {email} to superuser[/green]")

    console.rule("Promote user to superuser.")
    email = email or click.prompt("Email")
    anyio.run(_promote_to_superuser, typing_cast("str", email))


@user_management_group.command(name="create-roles", help="Create pre-configured application roles and assign to users.")
def create_default_roles() -> None:
    """Create the default roles for the system."""
    import anyio

    console = get_console()

    async def _create_default_roles() -> None:
        async with _provide_driver() as driver:
            created: list[str] = []
            for role_name, role_slug in (
                (DEFAULT_ACCESS_ROLE, DEFAULT_ROLE_SLUG),
                (SUPERUSER_ACCESS_ROLE, SUPERUSER_ROLE_SLUG),
            ):
                _, was_created = await _ensure_role(driver, name=role_name, slug=role_slug)
                if was_created:
                    created.append(role_name)

        if created:
            console.print(f"[green]created roles: {', '.join(created)}[/green]")
        else:
            console.print("[yellow]default roles already exist[/yellow]")

    console.rule("Creating default roles.")
    anyio.run(_create_default_roles)
