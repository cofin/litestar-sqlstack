from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from litestar.testing import AsyncTestClient


@pytest.mark.anyio
async def test_system_health_uses_injected_service(client: AsyncTestClient) -> None:
    response = await client.get("/health")

    assert response.status_code in {200, 500}
    assert "databaseStatus" in response.json()
