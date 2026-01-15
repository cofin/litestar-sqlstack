"""User Access Controllers."""

from __future__ import annotations

from typing import Annotated, Any

from litestar import Controller, Request, Response, post
from litestar.enums import RequestEncodingType
from litestar.params import Body

from sqlstack.domain.accounts import schemas as s
from sqlstack.domain.accounts.services import UserService
from sqlstack.lib.di import Inject, inject
from sqlstack.lib.schema import Message


class AccessController(Controller):
    """User login and registration."""

    tags = ["Access"]
    signature_types = [UserService, Message]

    @post(operation_id="AccountLogin", path="/api/access/login", exclude_from_auth=True)
    @inject
    async def login(
        self,
        request: Request[Any, Any, Any],
        users_service: Inject[UserService],
        data: Annotated[s.AccountLogin, Body(title="Login", media_type=RequestEncodingType.URL_ENCODED)],
    ) -> Response[s.User]:
        """Authenticate a user.

        Args:
            request: Request object
            data: Login credentials
            users_service: User Service

        Returns:
            Authenticated user
        """
        user = await users_service.authenticate(data.username, data.password)
        request.set_session({"user_id": str(user.id)})
        return Response(user, status_code=200)

    @post(operation_id="AccountLogout", path="/api/access/logout")
    async def logout(self, request: Request[s.User, Any, Any]) -> Response[Message]:
        """Account Logout

        Args:
            request: Request

        Returns:
            Logout Response
        """
        request.clear_session()
        return Response(Message(message="OK"), status_code=200)

    @post(operation_id="AccountRegister", path="/api/access/signup", exclude_from_auth=True)
    @inject
    async def signup(
        self, request: Request[Any, Any, Any], users_service: Inject[UserService], data: s.AccountRegister
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
