"""CLI configuration and styling."""

import rich_click as click

# Colors
SUCCESS_COLOR = "green"
WARNING_COLOR = "yellow"
ERROR_COLOR = "red"
INFO_COLOR = "cyan"

# Rich-click configuration
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.SHOW_METAVARS_COLUMN = False
click.rich_click.APPEND_METAVARS_HELP = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "italic"
click.rich_click.ERRORS_SUGGESTION = "Try running the '--help' flag for more information."
from rich.console import Console

console = Console()


def left_aligned_rule(title: str, style: str = "blue") -> None:
    """Print a left-aligned rule with title."""
    console.rule(title, style=style, align="left")
