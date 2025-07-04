# ruff: noqa: ARG001, RUF029
from __future__ import annotations

from typing import Any

import click


@click.group(name="users", invoke_without_command=False, help="Manage application users and roles.")
@click.pass_context
def user_management_group(_: dict[str, Any]) -> None:
    """Manage application users."""


@user_management_group.command(name="create-user", help="Create a user")
@click.option(
    "--email",
    help="Email of the new user",
    type=click.STRING,
    required=False,
    show_default=False,
)
@click.option(
    "--name",
    help="Full name of the new user",
    type=click.STRING,
    required=False,
    show_default=False,
)
@click.option(
    "--password",
    help="Password",
    type=click.STRING,
    required=False,
    show_default=False,
)
@click.option(
    "--superuser",
    help="Is a superuser",
    type=click.BOOL,
    default=False,
    required=False,
    show_default=False,
    is_flag=True,
)
def create_user(
    email: str | None,
    name: str | None,
    password: str | None,
    superuser: bool | None,
) -> None:
    """Create a user."""
    from typing import cast

    import anyio
    import click
    from rich import get_console

    console = get_console()

    async def _create_user(
        email: str,
        password: str,
        name: str | None = None,
        superuser: bool = False,
    ) -> None:
        console.print("TO BE IMPLEMENTED")

    console.rule("Create a new application user.")
    email = email or click.prompt("Email")
    name = name or click.prompt("Full Name", show_default=False)
    password = password or click.prompt("Password", hide_input=True, confirmation_prompt=True)
    superuser = superuser or click.prompt("Create as superuser?", show_default=True, type=click.BOOL)

    anyio.run(_create_user, cast("str", email), cast("str", password), name, cast("bool", superuser))


@user_management_group.command(name="promote-to-superuser", help="Promotes a user to application superuser")
@click.option(
    "--email",
    help="Email of the user",
    type=click.STRING,
    required=False,
    show_default=False,
)
def promote_to_superuser(email: str) -> None:
    """Promote to Superuser.

    Args:
        email (str): The email address of the user to promote.
    """
    import anyio
    from rich import get_console

    console = get_console()

    async def _promote_to_superuser(email: str) -> None:
        console.print("TO BE IMPLEMENTED")

    console.rule("Promote user to superuser.")
    anyio.run(_promote_to_superuser, email)


@user_management_group.command(name="create-roles", help="Create pre-configured application roles and assign to users.")
def create_default_roles() -> None:
    """Create the default Roles for the system

    Args:
        email (str): The email address of the user to promote.
    """
    import anyio
    from rich import get_console

    console = get_console()

    async def _create_default_roles() -> None:
        console.print("TO BE IMPLEMENTED")

    console.rule("Creating default roles.")
    anyio.run(_create_default_roles)
