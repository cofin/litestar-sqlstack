import click
import psycopg

from sqlstack.lib.settings import get_settings
from tools.lib.db_url import make_postgres_url


@click.command(name="create-db")
def create_db_cmd() -> None:
    """Create the database if it does not exist."""
    settings = get_settings()
    url = make_postgres_url(
        user=settings.db.USER,
        password=settings.db.PASSWORD,
        host=settings.db.HOST,
        port=settings.db.PORT,
        database="postgres",
    )
    try:
        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.db.DATABASE,))
            if cur.fetchone():
                click.echo(f"Database '{settings.db.DATABASE}' already exists.")
                return
            cur.execute(f"CREATE DATABASE {settings.db.DATABASE}")
            click.secho(f"✓ Database '{settings.db.DATABASE}' created successfully.", fg="green")
    except Exception as e:
        raise click.ClickException(f"Failed to create database: {e}") from e

@click.command(name="drop-db")
@click.option("--yes", "-y", is_flag=True, help="Confirm drop without prompting.")
def drop_db_cmd(yes: bool) -> None:
    """Drop the database."""
    settings = get_settings()
    if not yes and not click.confirm(f"Are you sure you want to drop the database '{settings.db.DATABASE}'?"):
        return
    url = make_postgres_url(
        user=settings.db.USER,
        password=settings.db.PASSWORD,
        host=settings.db.HOST,
        port=settings.db.PORT,
        database="postgres",
    )
    try:
        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {settings.db.DATABASE}")
            click.secho(f"✓ Database '{settings.db.DATABASE}' dropped.", fg="green")
    except Exception as e:
        raise click.ClickException(f"Failed to drop database: {e}") from e
