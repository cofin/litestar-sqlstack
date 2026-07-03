#!/usr/bin/env python3
import rich_click as click
from tools.cli.init import init_command
from tools.cli.doctor import doctor_command
from tools.cli.install import install_command
from tools.cli.infra import infra_group
from tools.cli.clean import clean_command
from tools.cli.destroy import destroy_command
from tools.postgres.cli.connection import test_connection_cmd
from tools.postgres.cli.database import create_db_cmd, drop_db_cmd
from tools.postgres.cli.health import health_cmd
from sqlspec.cli import add_migration_commands

@click.group(name="manage")
def manage_cli() -> None:
    """DevOps CLI management tool for litestar-sqlstack."""

@click.group(name="database")
@click.pass_context
def database_group(ctx: click.Context) -> None:
    """Database operations and migrations."""
    from sqlstack.config import db
    ctx.ensure_object(dict)
    ctx.obj["configs"] = [db]

database_group.add_command(test_connection_cmd)
database_group.add_command(create_db_cmd)
database_group.add_command(drop_db_cmd)
database_group.add_command(health_cmd)

add_migration_commands(database_group)

manage_cli.add_command(init_command)
manage_cli.add_command(doctor_command)
manage_cli.add_command(install_command)
manage_cli.add_command(infra_group)
manage_cli.add_command(clean_command)
manage_cli.add_command(destroy_command)
manage_cli.add_command(database_group)

if __name__ == "__main__":
    manage_cli()
