import socket

import click

from tools.lib.container import ContainerRuntime, ContainerRuntimeError
from tools.postgres.database import DatabaseConfig


def is_port_in_use(port: int) -> bool:
    """Check if a network port is already in use on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True

@click.command(name="doctor")
def doctor_command() -> None:
    """Run diagnostics to verify system readiness."""
    click.echo("Running diagnostics...")
    success = True

    try:
        runtime = ContainerRuntime()
        click.secho(f"✓ Container runtime: {runtime.name} ({runtime.path})", fg="green")
    except ContainerRuntimeError as e:
        click.secho(f"✗ No container runtime detected: {e}", fg="red")
        success = False

    config = DatabaseConfig()
    if is_port_in_use(config.port):
        click.secho(f"✗ Port {config.port} is already in use. Cannot bind database.", fg="red")
        success = False
    else:
        click.secho(f"✓ Database port {config.port} is available.", fg="green")

    if not success:
        raise click.ClickException("Diagnostics failed. Please fix the issues above.")
    click.secho("System is healthy and ready!", fg="green")
