import click

from tools.lib.container import ContainerRuntime
from tools.postgres.database import PostgreSQLDatabase


@click.group(name="infra")
def infra_group() -> None:
    """Manage local infrastructure containers."""

@infra_group.command(name="start")
def infra_start() -> None:
    """Start local infrastructure containers."""
    click.echo("Starting local infrastructure...")
    runtime = ContainerRuntime()
    db = PostgreSQLDatabase(runtime)
    try:
        db.start()
        click.secho("Local infrastructure is ready! 🚀", fg="green")
    except Exception as e:
        raise click.ClickException(f"Failed to start infrastructure: {e}") from e

@infra_group.command(name="stop")
def infra_stop() -> None:
    """Stop local infrastructure containers."""
    click.echo("Stopping local infrastructure...")
    runtime = ContainerRuntime()
    db = PostgreSQLDatabase(runtime)
    try:
        db.stop()
        click.secho("Local infrastructure stopped. 🛑", fg="green")
    except Exception as e:
        raise click.ClickException(f"Failed to stop infrastructure: {e}") from e

@infra_group.command(name="restart")
def infra_restart() -> None:
    """Restart local infrastructure containers."""
    click.echo("Restarting local infrastructure...")
    runtime = ContainerRuntime()
    db = PostgreSQLDatabase(runtime)
    try:
        db.restart()
        click.secho("Local infrastructure restarted! 🚀", fg="green")
    except Exception as e:
        raise click.ClickException(f"Failed to restart infrastructure: {e}") from e

@infra_group.command(name="status")
def infra_status() -> None:
    """Show the status of local infrastructure containers."""
    runtime = ContainerRuntime()
    db = PostgreSQLDatabase(runtime)
    status = db.status()
    click.echo(f"Database status: {status}")

@infra_group.command(name="remove")
def infra_remove() -> None:
    """Remove local infrastructure containers."""
    click.echo("Removing local infrastructure containers...")
    runtime = ContainerRuntime()
    db = PostgreSQLDatabase(runtime)
    try:
        db.remove()
        click.secho("Local infrastructure containers removed.", fg="green")
    except Exception as e:
        raise click.ClickException(f"Failed to remove infrastructure: {e}") from e
