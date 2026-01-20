from __future__ import annotations

from dataclasses import fields

import pytest

from sqlstack.lib import di


def test_query_context_dataclass() -> None:
    query_context = di.QueryContext(query_id="abc123")

    assert query_context.query_id == "abc123"
    # dataclass should only expose the declared field
    assert [f.name for f in fields(di.QueryContext)] == ["query_id"]


def test_query_id_var_round_trip() -> None:
    assert di.query_id_var.get() is None

    token = di.query_id_var.set("request-123")
    try:
        assert di.query_id_var.get() == "request-123"
    finally:
        di.query_id_var.reset(token)

    assert di.query_id_var.get() is None


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
        "get_from_connection",
        "inject",
        "make_async_container",
        "make_container",
        "provide",
        "query_id_var",
        "setup_dishka",
    }

    assert set(di.__all__) == expected_exports


@pytest.mark.anyio
async def test_make_litestar_container_lifecycle() -> None:
    from sqlstack.ioc import make_litestar_container

    container = make_litestar_container()
    try:
        assert hasattr(container, "get")
    finally:
        await container.close()
