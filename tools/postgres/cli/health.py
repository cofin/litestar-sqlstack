import click

from sqlstack.lib.settings import get_settings
from tools.postgres.database import PostgreSQLDatabase


@click.command(name="health")
def health_cmd() -> None:
    """Check the database container status and connection health."""
    settings = get_settings()
    url = settings.db.get_connection_string()

    click.echo("Checking database health...")
    if PostgreSQLDatabase.verify_connection(url):
        click.secho("✓ Database wire connection is healthy.", fg="green")
    else:
        click.secho("✗ Database wire connection failed.", fg="red")
        raise click.ClickException("Database health check failed.")
