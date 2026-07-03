import secrets
from pathlib import Path

import click


def init_env(env_file: Path, example_file: Path) -> None:
    """Helper for programmatic initialization."""
    content = example_file.read_text()
    secret_key = secrets.token_hex(16)
    lines = []
    for line in content.splitlines():
        if line.startswith("SECRET_KEY="):
            lines.append(f"SECRET_KEY={secret_key}")
        else:
            lines.append(line)
    env_file.write_text("\n".join(lines) + "\n")

@click.command(name="init")
@click.option("--force", is_flag=True, help="Force overwrite existing .env file.")
def init_command(force: bool) -> None:
    """Initialize development environment configuration."""
    target_env = Path(".env")
    source_example = Path(".env.example")

    if target_env.exists() and not force:
        click.echo(".env file already exists. Use --force to overwrite.")
        return

    if not source_example.exists():
        raise click.ClickException(f"Template file {source_example} not found.")

    init_env(target_env, source_example)
    click.echo("Initialized .env file with a fresh SECRET_KEY.")
