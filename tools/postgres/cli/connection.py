import click

from sqlstack.lib.settings import get_settings
from tools.postgres.database import PostgreSQLDatabase


@click.command(name="test-connection")
def test_connection_cmd() -> None:
    """Test PostgreSQL connection."""
    settings = get_settings()
    url = settings.db.get_connection_string()
    click.echo(f"Testing connection to: {settings.db.HOST}:{settings.db.PORT}...")
    if PostgreSQLDatabase.verify_connection(url):
        click.secho("✓ Connection successful!", fg="green")
    else:
        click.secho("✗ Connection failed.", fg="red")
        raise click.ClickException("Could not connect to database.")
