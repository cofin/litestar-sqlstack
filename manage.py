#!/usr/bin/env python3
import click

from tools.cli.doctor import doctor_command
from tools.cli.infra import infra_group
from tools.cli.init import init_command
from tools.cli.install import install_command


@click.group(name="manage")
def manage_cli() -> None:
    """DevOps CLI management tool for litestar-sqlstack."""

manage_cli.add_command(init_command)
manage_cli.add_command(doctor_command)
manage_cli.add_command(install_command)
manage_cli.add_command(infra_group)

if __name__ == "__main__":
    manage_cli()
