from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import fields
from unittest.mock import AsyncMock, MagicMock

import pytest

from sqlstack.lib import di


# --- Existing tests (preserved) ---

def test_query_context_dataclass() -> None:
    query_context = di.QueryContext(query_id="abc123")
    assert query_context.query_id == "abc123"
    assert [f.name for f in fields(di.QueryContext)] == ["query_id"]


def test_query_id_var_round_trip() -> None:
    assert di.query_id_var.get() is None
    token = di.query_id_var.set("request-123")
    try:
        assert di.query_id_var.get() == "request-123"
    finally:
        di.query_id_var.reset(token)
    assert di.query_id_var.get() is None


@pytest.mark.anyio
async def test_make_litestar_container_lifecycle() -> None:
    from sqlstack.ioc import make_litestar_container
    container = make_litestar_container()
    try:
        assert hasattr(container, "get")
    finally:
        await container.close()


# --- Updated exports test ---

def test_public_exports_match_expected() -> None:
    expected_exports = {
        "AsyncContainer",
        "Container",
        "Inject",
        "LitestarProvider",
        "LitestarRouter",
        "Provider",
        "QueryContext",
        "Scope",
        "WebSocketScope",
        "get_from_connection",
        "inject",
        "job_inject",
        "make_async_container",
        "make_container",
        "provide",
        "provide_websocket_scope",
        "query_id_var",
        "request_container_var",
        "setup_dishka",
        "with_websocket_request",
        "worker_container_var",
        "worker_scope",
    }
    assert set(di.__all__) == expected_exports


# --- New WebSocket DI tests ---

@pytest.mark.anyio
async def test_with_websocket_request_creates_request_scope() -> None:
    """with_websocket_request should create a child REQUEST scope from the SESSION container."""
    mock_request_container = AsyncMock()

    # Dishka's AsyncContainer.__call__ returns an async context manager
    # We simulate this by making the mock callable return an async CM
    @asynccontextmanager
    async def fake_enter_scope(*args, **kwargs):
        yield mock_request_container

    mock_session_container = MagicMock(side_effect=fake_enter_scope)

    mock_connection = MagicMock()
    mock_connection.state.dishka_container = mock_session_container

    async with di.with_websocket_request(mock_connection) as container:
        assert container is mock_request_container
    # Verify it was called with scope=REQUEST
    mock_session_container.assert_called_once()


def test_websocket_scope_factory() -> None:
    """WebSocketScope should be creatable from a connection."""
    mock_socket = MagicMock()
    scope = di.WebSocketScope(mock_socket)
    assert scope._connection is mock_socket


def test_provide_websocket_scope_returns_instance() -> None:
    """provide_websocket_scope should return a WebSocketScope."""
    mock_socket = MagicMock()
    result = di.provide_websocket_scope(mock_socket)
    assert isinstance(result, di.WebSocketScope)


@pytest.mark.anyio
async def test_worker_scope_raises_without_container() -> None:
    """worker_scope should raise RuntimeError when no worker container is set."""
    token = di.worker_container_var.set(None)
    try:
        with pytest.raises(RuntimeError, match="No worker container"):
            async with di.worker_scope():
                pass
    finally:
        di.worker_container_var.reset(token)
