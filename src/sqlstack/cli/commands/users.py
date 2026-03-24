"""User management CLI commands.

This module provides CLI commands for:
- Creating users
- Promoting users to superuser
- Creating default roles

All commands use the @async_inject decorator for automatic dependency injection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import rich_click as click
from rich import get_console
from sqlspec import sql
from sqlspec.utils.text import slugify

from sqlstack.config import DEFAULT_ACCESS_ROLE, SUPERUSER_ACCESS_ROLE
from sqlstack.domain.accounts.schemas import UserCreate
from sqlstack.utils.cli_tools import async_inject

if TYPE_CHECKING:
    from sqlspec.adapters.asyncpg import AsyncpgDriver

    from sqlstack.domain.accounts.services import UserRoleService, UserService

DEFAULT_ROLE_SLUG = slugify(DEFAULT_ACCESS_ROLE)
SUPERUSER_ROLE_SLUG = slugify(SUPERUSER_ACCESS_ROLE)


# ─────────────────────────────────────────────────────────────────────────────
# Role Helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _ensure_role(
    driver: AsyncpgDriver, *, name: str, slug: str, description: str | None = None
) -> tuple[UUID, bool]:
    """Ensure a role exists, creating it if necessary.

    Returns:
        Tuple of (role_id, was_created).
    """
    existing = await driver.select_one_or_none(sql.select("id").from_("role").where_eq("slug", slug))
    if existing:
        return cast("UUID", existing["id"]), False

    result = await driver.select_one(
        sql
        .insert("role")
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
    """Ensure a user has a role assigned.

    Returns:
        True if role was newly assigned, False if already had it.
    """
    if await service.user_has_role_by_slug(user_id, role_slug):
        return False
    await service.assign_role_to_user(user_id, role_id)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# User Management Commands
# ─────────────────────────────────────────────────────────────────────────────


@click.group(name="users", invoke_without_command=False, help="Manage application users and roles.")
@click.pass_context  # type: ignore[arg-type]
def user_management_group(_: dict[str, Any]) -> None:
    """Manage application users."""


@user_management_group.command(name="create-user", help="Create a user")
@click.option("--email", help="Email of the new user", type=click.STRING, required=False, show_default=False)  # pyright: ignore
@click.option("--name", help="Full name of the new user", type=click.STRING, required=False, show_default=False)  # pyright: ignore
@click.option("--password", help="Password", type=click.STRING, required=False, show_default=False)  # pyright: ignore
@click.option(  # pyright: ignore
    "--superuser",
    help="Create as a superuser",
    type=click.BOOL,
    default=False,
    required=False,
    show_default=False,
    is_flag=True,
)
@async_inject
async def create_user(
    driver: AsyncpgDriver,
    user_service: UserService,
    user_role_service: UserRoleService,
    email: str | None,
    name: str | None,
    password: str | None,
    superuser: bool | None,
) -> None:
    """Create a user."""
    console = get_console()
    console.rule("Create a new application user.")

    # Prompt for missing values
    email = email or click.prompt("Email")
    name = name or click.prompt("Full Name", show_default=False)
    password = password or click.prompt("Password", hide_input=True, confirmation_prompt=True)
    superuser = superuser or click.prompt("Create as superuser?", show_default=True, type=click.BOOL)

    async with user_service.begin_transaction():
        user = await user_service.create_user(
            UserCreate(
                email=cast("str", email),
                password=cast("str", password),
                name=name,
                is_superuser=bool(superuser),
                is_active=True,
                is_verified=bool(superuser),
            )
        )

        if superuser:
            role_id, created_role = await _ensure_role(driver, name=SUPERUSER_ACCESS_ROLE, slug=SUPERUSER_ROLE_SLUG)
            assigned_role = await _ensure_user_role_assignment(
                user_role_service, user_id=user.id, role_id=role_id, role_slug=SUPERUSER_ROLE_SLUG
            )
            if created_role:
                console.print(f"[green]created role: {SUPERUSER_ACCESS_ROLE}[/green]")
            if assigned_role:
                console.print(f"[green]assigned superuser role to {email}[/green]")

    console.print(f"[green]created user {user.email}[/green]")


@user_management_group.command(name="promote-to-superuser", help="Promotes a user to application superuser")
@click.option("--email", help="Email of the user", type=click.STRING, required=False, show_default=False)  # pyright: ignore
@async_inject
async def promote_to_superuser(driver: AsyncpgDriver, user_role_service: UserRoleService, email: str | None) -> None:
    """Promote a user to superuser."""
    console = get_console()
    console.rule("Promote user to superuser.")

    email = email or click.prompt("Email")

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
        user_role_service, user_id=user_id, role_id=role_id, role_slug=SUPERUSER_ROLE_SLUG
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


@user_management_group.command(name="create-roles", help="Create pre-configured application roles and assign to users.")
@async_inject
async def create_default_roles(driver: AsyncpgDriver) -> None:
    """Create the default roles for the system."""
    console = get_console()
    console.rule("Creating default roles.")

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
