"""OAuth account management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from httpx_oauth.clients.github import GitHubOAuth2
from httpx_oauth.clients.google import GoogleOAuth2
from litestar import Controller, delete, get, post
from litestar.exceptions import HTTPException
from litestar.params import Dependency, Parameter
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from sqlalchemy.orm import undefer_group

from sqlstack.domain.accounts import schemas as s
from sqlstack.domain.accounts.services import UserService
from sqlstack.domain.accounts.services._user_oauth_account import UserOAuthAccountService
from sqlstack.domain.accounts.auth import create_oauth_state
from sqlstack.lib.di import Inject
from sqlstack.lib.schema import Message
from sqlstack.lib.service import FilterTypes, OffsetPagination
from sqlstack.lib.settings import AppSettings

if TYPE_CHECKING:
    from litestar import Request

OAUTH_DEFAULT_SCOPES: dict[str, list[str]] = {
    "google": ["openid", "email", "profile"],
    "github": ["read:user", "user:email"],
}


def _get_oauth_client(provider: str, settings: AppSettings) -> GoogleOAuth2 | GitHubOAuth2:
    """Return an OAuth client for the requested provider.

    Raises:
        HTTPException: If the provider is unsupported or not configured.
    """
    if provider == "google":
        if not settings.GOOGLE_OAUTH2_CLIENT_ID or not settings.GOOGLE_OAUTH2_CLIENT_SECRET:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Google OAuth is not configured")
        return GoogleOAuth2(
            client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
        )
    if provider == "github":
        if not settings.GITHUB_OAUTH2_CLIENT_ID or not settings.GITHUB_OAUTH2_CLIENT_SECRET:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="GitHub OAuth is not configured")
        return GitHubOAuth2(
            client_id=settings.GITHUB_OAUTH2_CLIENT_ID,
            client_secret=settings.GITHUB_OAUTH2_CLIENT_SECRET,
        )
    raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=f"Unknown OAuth provider: {provider}")


class OAuthAccountController(Controller):
    """OAuth account management for profile settings."""

    path = "/api/profile/oauth"
    tags = ["Profile"]

    @get(operation_id="ProfileOAuthAccounts", path="/accounts")
    async def list_accounts(
        self,
        current_user: s.User,
        oauth_account_service: Inject[UserOAuthAccountService],
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[s.OAuthAccountInfo]:
        """List linked OAuth accounts.

        Args:
            current_user: The authenticated user.
            oauth_account_service: OAuth account service.
            filters: Filter and pagination parameters.

        Returns:
            Linked OAuth accounts.
        """
        accounts, total = await oauth_account_service.list_and_count(
            *filters,
            user_id=current_user.id,
        )
        items = [
            {
                "provider": account.oauth_name,
                "oauthId": account.account_id,
                "email": account.account_email,
                "name": None,
                "avatarUrl": None,
                "linkedAt": account.created_at,
                "lastLoginAt": None, # account.last_login_at (schema update needed if used)
            }
            for account in accounts
        ]
        return oauth_account_service.to_schema(
            data=items,
            total=total,
            filters=filters,
            schema_type=s.OAuthAccountInfo,
        )

    @post(operation_id="ProfileOAuthLink", path="/{provider:str}/link")
    async def start_link(
        self,
        request: Request[Any, Any, Any],
        current_user: s.User,
        settings: AppSettings,
        provider: str,
        redirect_url: str | None = Parameter(query="redirect_url", required=False),
    ) -> s.OAuthAuthorization:
        """Start OAuth linking flow.

        Uses the main auth callback URL so only one callback needs to be registered
        with the OAuth provider. The 'link' action in state triggers account linking.

        Args:
            request: The request object.
            current_user: The authenticated user.
            settings: Application settings.
            provider: OAuth provider name.
            redirect_url: Frontend callback URL after linking.

        Returns:
            Authorization URL and state.
        """
        client = _get_oauth_client(provider, settings)
        frontend_callback = redirect_url or f"{settings.URL}/profile"
        state = create_oauth_state(
            provider=provider,
            redirect_url=frontend_callback,
            secret_key=settings.SECRET_KEY,
            action="link",
            user_id=str(current_user.id),
        )
        # Use the main auth callback URL (same as login flow)
        # The 'link' action in state tells the callback to link instead of login
        callback_url = str(request.url_for(f"oauth:{provider}:callback"))
        authorization_url = await client.get_authorization_url(
            redirect_uri=callback_url,
            state=state,
            scope=OAUTH_DEFAULT_SCOPES.get(provider, []),
        )
        return s.OAuthAuthorization(authorization_url=authorization_url, state=state)

    @delete(operation_id="ProfileOAuthUnlink", path="/{provider:str}", status_code=200)
    async def unlink(
        self,
        current_user: s.User,
        users_service: Inject[UserService],
        oauth_account_service: Inject[UserOAuthAccountService],
        provider: str,
    ) -> Message:
        """Unlink an OAuth provider from the user's account.

        Args:
            current_user: The authenticated user.
            users_service: User service.
            oauth_account_service: OAuth account service.
            provider: OAuth provider name.

        Raises:
            HTTPException: If unlink is not allowed or provider not found.

        Returns:
            Success message.
        """
        user = await users_service.get_user(current_user.id)
        # user has has_password prop already on schema, or we rely on get_user to return model with password hash if needed for checking
        # But UserService.get_user returns schema s.User.
        # UserOAuthAccountService.can_unlink_oauth checks user.has_password (boolean).
        
        can_unlink, reason = await oauth_account_service.can_unlink_oauth(user)
        if not can_unlink:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=reason)

        success = await oauth_account_service.unlink_oauth_account(user_id=current_user.id, provider=provider)
        if not success:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"No {provider} account linked to your profile",
            )

        return Message(message=f"Successfully unlinked {provider} account")

    @post(operation_id="ProfileOAuthUpgradeScopes", path="/{provider:str}/upgrade-scopes")
    async def upgrade_scopes(
        self,
        request: Request[Any, Any, Any],
        current_user: s.User,
        settings: AppSettings,
        provider: str,
        redirect_url: str | None = Parameter(query="redirect_url", required=False),
    ) -> s.OAuthAuthorization:
        """Request expanded OAuth scopes via re-authorization.

        Args:
            request: The request object.
            current_user: The authenticated user.
            settings: Application settings.
            provider: OAuth provider name.
            redirect_url: Frontend callback URL after upgrade.

        Returns:
            Authorization URL and state.
        """
        client = _get_oauth_client(provider, settings)
        frontend_callback = redirect_url or f"{settings.URL}/profile"
        state = create_oauth_state(
            provider=provider,
            redirect_url=frontend_callback,
            secret_key=settings.SECRET_KEY,
            action="upgrade",
            user_id=str(current_user.id),
        )
        # Use the main auth callback URL (same as login flow)
        callback_url = str(request.url_for(f"oauth:{provider}:callback"))
        authorization_url = await client.get_authorization_url(
            redirect_uri=callback_url,
            state=state,
            scope=OAUTH_DEFAULT_SCOPES.get(provider, []),
        )
        return s.OAuthAuthorization(authorization_url=authorization_url, state=state)
