import shutil
from pathlib import Path

import click


@click.command(name="destroy")
def destroy_command() -> None:
    """Destroy the virtual environment."""
    click.echo("Destroying virtual environment...")
    venv_path = Path(".venv")
    if venv_path.exists():
        shutil.rmtree(venv_path, ignore_errors=True)
        click.secho("✓ Virtual environment destroyed.", fg="green")
    else:
        click.echo("No virtual environment found.")
