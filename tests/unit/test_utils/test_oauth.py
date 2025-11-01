from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx_oauth.oauth2 import BaseOAuth2, GetAccessTokenError, OAuth2Error, OAuth2Token

from sqlstack.utils.oauth import OAuth2AuthorizeCallback, OAuth2AuthorizeCallbackError, OAuth2ProviderPlugin

if TYPE_CHECKING:
    from litestar import Request


class DummyRequest:
    def __init__(self) -> None:
        self.called_with: list[str] = []

    def url_for(self, route_name: str) -> str:
        self.called_with.append(route_name)
        return f"https://example.test/{route_name}"


def make_oauth_client() -> BaseOAuth2[OAuth2Token]:
    client = cast("BaseOAuth2[OAuth2Token]", AsyncMock())
    client.get_access_token = AsyncMock()  # type: ignore[method-assign]
    return client


def test_oauth2_authorize_callback_error_behaves_like_http_exception() -> None:
    err = OAuth2AuthorizeCallbackError(status_code=400, detail="invalid")

    assert isinstance(err, OAuth2Error)
    assert err.status_code == 400
    assert err.detail == "invalid"


@pytest.mark.anyio
async def test_authorize_callback_requires_code_parameter() -> None:
    callback = OAuth2AuthorizeCallback(client=make_oauth_client(), route_name="callback")

    with pytest.raises(OAuth2AuthorizeCallbackError):
        await callback(
            cast("Request[Any,Any,Any]", DummyRequest()), code=None, code_verifier=None, callback_state=None, error=None
        )


@pytest.mark.anyio
async def test_authorize_callback_raises_on_remote_error() -> None:
    callback = OAuth2AuthorizeCallback(client=make_oauth_client(), route_name="callback")

    with pytest.raises(OAuth2AuthorizeCallbackError):
        await callback(
            cast("Request[Any,Any,Any]", DummyRequest()),
            code="ignored",
            code_verifier=None,
            callback_state=None,
            error="access_denied",
        )


@pytest.mark.anyio
async def test_authorize_callback_fetches_access_token() -> None:
    client = make_oauth_client()
    token: OAuth2Token = cast("OAuth2Token", {"access_token": "token", "token_type": "bearer"})
    cast("AsyncMock", client.get_access_token).return_value = token

    callback = OAuth2AuthorizeCallback(client=client, route_name="callback")
    request = cast("Request[Any,Any,Any]", DummyRequest())

    result = await callback(request, code="auth-code", code_verifier="verifier", callback_state="abc", error=None)

    assert isinstance(result, tuple)
    returned_token, state = result
    assert returned_token == token
    assert state == "abc"
    assert request.called_with == ["callback"]  # pyright: ignore
    cast("AsyncMock", client.get_access_token).assert_awaited_once()


@pytest.mark.anyio
async def test_authorize_callback_wraps_access_token_errors() -> None:
    client = make_oauth_client()
    cast("AsyncMock", client.get_access_token).side_effect = GetAccessTokenError("boom", response=None)

    callback = OAuth2AuthorizeCallback(client=client, route_name="callback")

    with pytest.raises(OAuth2AuthorizeCallbackError) as exc_info:
        await callback(
            cast("Request[Any,Any,Any]", DummyRequest()),
            code="auth",
            code_verifier=None,
            callback_state=None,
            error=None,
        )

    assert "boom" in str(exc_info.value.detail)


def test_oauth2_provider_plugin_updates_signature_namespace() -> None:
    plugin = OAuth2ProviderPlugin()
    app_config = MagicMock()
    app_config.signature_namespace = {}

    result = plugin.on_app_init(app_config)

    assert result.signature_namespace["OAuth2AuthorizeCallback"] is OAuth2AuthorizeCallback
    assert "AccessTokenState" in result.signature_namespace
