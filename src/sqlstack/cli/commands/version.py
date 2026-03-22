"""Version command."""

import rich_click as click
from rich.console import Console

from sqlstack.__metadata__ import __version__

console = Console()


@click.command(name="version", help="Show SQLStack version information")
def version_cmd() -> None:
    """Show SQLStack version information."""
    console.print(f"SQLStack [cyan]v{__version__}[/cyan]")
