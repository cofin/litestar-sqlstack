"""CLI utilities for async command injection."""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast, get_type_hints

import rich_click as click

from sqlstack.utils.sync_tools import run_

if TYPE_CHECKING:
    from dishka import AsyncContainer

P = ParamSpec("P")
R = TypeVar("R")


def async_inject(func: Callable[P, Awaitable[R]]) -> Callable[P, R]:
    """Decorator to run async commands with Dishka injection.

    Automatically inspects type hints and injects dependencies from the container.
    Dependencies are resolved based on the function's type annotations.

    Example:
        @click.command()
        @async_inject
        async def my_command(user_service: UserService, name: str) -> None:
            # user_service is automatically injected from DI container
            # name comes from click option/argument
            user = await user_service.get_by_name(name)

    Args:
        func: Async function to wrap with DI injection.

    Returns:
        Synchronous wrapper that handles async execution and DI.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        async def _runner() -> R:
            ctx = click.get_current_context()
            if ctx is None:
                msg = "No click context found"
                raise RuntimeError(msg)

            ctx_obj = cast("dict[str, Any]", ctx.obj) if ctx.obj else {}
            container_factory = ctx_obj.get("container_factory")

            if not container_factory:
                from sqlstack.ioc import make_cli_container

                container_factory = make_cli_container

            container = cast("AsyncContainer", container_factory())
            try:
                async with container() as request_container:
                    type_hints = get_type_hints(func)
                    injected_kwargs: dict[str, Any] = {}

                    for name, type_hint in type_hints.items():
                        if name in kwargs:
                            continue
                        if name != "return":
                            try:
                                dep = await request_container.get(type_hint)
                                injected_kwargs[name] = dep
                            except Exception:  # noqa: BLE001, S110
                                pass

                    final_kwargs = {**kwargs, **injected_kwargs}
                    return await func(*args, **final_kwargs)
            finally:
                await container.close()

        return run_(_runner)()

    return wrapper


__all__ = ("async_inject",)
