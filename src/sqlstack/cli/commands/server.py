"""Server management commands."""

import sys
from typing import Any

import rich_click as click
from litestar.cli._utils import LitestarEnv
from litestar_granian.cli import run_command as litestar_run_command
from rich.console import Console
from rich.table import Table

from sqlstack.cli.utils import async_inject
from sqlstack.domain.system.services import TaskService
from sqlstack.server.asgi import create_app
from sqlstack.utils.worker import Worker

console = Console()


class ServerGroup(click.RichGroup):
    """Custom click group that provides app context for server commands."""

    def invoke(self, ctx: click.Context) -> None:
        """Set up the Litestar app in context before invoking subcommands."""
        app = create_app()
        env = LitestarEnv.from_env("sqlstack.server.asgi:create_app")
        env.app = app
        ctx.obj = env
        super().invoke(ctx)


@click.group(name="server", help="API server and worker management", cls=ServerGroup)
def server_group() -> None:
    """API server and worker management commands."""


def _create_run_command() -> click.Command:
    """Create a run command that wraps litestar_granian with our app."""
    original_command = litestar_run_command

    @click.pass_context  # type: ignore[arg-type]
    def wrapped_run(ctx: click.Context, **kwargs: Any) -> None:
        """Run the API server using litestar-granian."""

        env = ctx.ensure_object(LitestarEnv)
        if original_command.callback:
            original_command.callback(app=env.app, ctx=ctx, **kwargs)

    new_command = click.command(name="run", help=original_command.help)(wrapped_run)
    new_command.params = original_command.params.copy()

    return new_command


server_group.add_command(_create_run_command())


@server_group.command(name="run-worker")
@click.option("--poll-interval", default=30.0, type=float, help="Seconds between polling for tasks (default: 30)")
@click.option("--batch-size", default=10, type=int, help="Maximum tasks to process per poll")
@click.option(
    "--shutdown-timeout", default=30.0, type=float, help="Maximum time to wait for tasks to complete on shutdown"
)
@async_inject
async def run_worker(poll_interval: float, batch_size: int, shutdown_timeout: float) -> None:
    """Run only the background worker process."""
    try:
        console.print("[green]Starting worker process...[/green]")
        worker = Worker(poll_interval=poll_interval, batch_size=batch_size, shutdown_timeout=shutdown_timeout)
        await worker.start()
    except KeyboardInterrupt:
        console.print("[yellow]Worker stopped by user[/yellow]")
        sys.exit(0)


@server_group.command(name="status")
@async_inject
async def status(task_service: TaskService) -> None:
    """Show task queue status."""
    try:
        stats = await task_service.get_statistics()

        table = Table(title="Task Queue Status")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="green")

        for status_name, count in stats.items():
            table.add_row(status_name, str(count))

        console.print(table)

    except (ConnectionError, ImportError, RuntimeError, OSError) as e:
        console.print(f"[red]Error getting task status: {e}[/red]")
        sys.exit(1)
