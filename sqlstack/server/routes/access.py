"""User Access Controllers."""

from __future__ import annotations

from typing import Annotated, Any

from litestar import Controller, Request, Response, post
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.security.jwt import OAuth2Login, Token

from sqlstack import schemas as s
from sqlstack.lib.di import Inject, inject
from sqlstack.server import security
from sqlstack.services import UserService


class AccessController(Controller):
    """User login and registration."""

    tags = ["Access"]
    signature_types = [UserService, OAuth2Login, Token]

    @post(operation_id="AccountLogin", path="/api/access/login", exclude_from_auth=True)
    @inject
    async def login(
        self,
        users_service: Inject[UserService],
        data: Annotated[s.AccountLogin, Body(title="OAuth2 Login", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> Response[OAuth2Login]:
        """Authenticate a user.

        Args:
            data: OAuth2 Login Data
            users_service: User Service

        Returns:
            OAuth2 Login Response
        """
        user = await users_service.authenticate(data.username, data.password)
        return security.auth.login(user.email)

    @post(operation_id="AccountLogout", path="/api/access/logout")
    async def logout(self, request: Request[s.User, Token, Any]) -> Response[s.Message]:
        """Account Logout

        Args:
            request: Request

        Returns:
            Logout Response
        """
        request.cookies.pop(security.auth.key, None)
        request.clear_session()
        response = Response(s.Message(message="OK"), status_code=200)
        response.delete_cookie(security.auth.key)
        return response

    @post(operation_id="AccountRegister", path="/api/access/signup")
    @inject
    async def signup(
        self, request: Request[s.User, Token, Any], users_service: Inject[UserService], data: s.AccountRegister
    ) -> s.User:
        """User Signup.

        Args:
            request: Request
            users_service: User Service
            data: Account Register Data

        Returns:
            User
        """
        user = await users_service.create_user(data)
        request.app.emit(event_id="user_created", user_id=user.id)
        return user
