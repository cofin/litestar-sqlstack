import shutil
import subprocess

import click


@click.command(name="install")
def install_command() -> None:
    """Install project dependencies and setup developer environment."""
    click.echo("Installing dependencies...")

    click.echo("Syncing Python packages...")
    try:
        subprocess.run(["uv", "sync", "--all-extras", "--dev"], check=True)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Failed to sync Python dependencies: {e}") from e

    if not shutil.which("npm"):
        click.echo("Node not detected. Installing Node environment into venv...")
        try:
            subprocess.run(["uvx", "nodeenv", ".venv", "--force", "--quiet"], check=True)
        except subprocess.CalledProcessError as e:
            raise click.ClickException(f"Failed to install nodeenv: {e}") from e
    else:
        click.echo("Node already installed on this machine, skipping nodeenv setup.")

    click.echo("Setting up prek...")
    try:
        subprocess.run(["uv", "run", "prek", "install"], check=True)
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"Failed to setup prek: {e}") from e

    click.secho("Installation complete! 🎉", fg="green")
