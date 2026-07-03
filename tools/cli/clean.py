import shutil
from pathlib import Path

import click


@click.command(name="clean")
def clean_command() -> None:
    """Cleanup temporary build and test artifacts."""
    click.echo("Cleaning working directory...")
    patterns = [
        "pytest_cache", ".ruff_cache", ".hypothesis", "build", "dist",
        ".eggs", ".coverage", "coverage.xml", "coverage.json", "htmlcov",
        ".pytest_cache", ".mypy_cache", ".unasyncd_cache", ".auto_pytabs_cache",
        "node_modules", "src/js/node_modules", "docs/_build"
    ]
    for pat in patterns:
        path = Path(pat)
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)

    for p in Path().rglob("*.py[co]"):
        p.unlink(missing_ok=True)
    for p in Path().rglob("__pycache__"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)

    click.secho("✓ Working directory cleaned.", fg="green")
