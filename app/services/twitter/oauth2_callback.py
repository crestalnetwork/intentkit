"""Twitter OAuth2 callback handler."""

from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse

import tweepy
from fastapi import APIRouter
from starlette.responses import JSONResponse, RedirectResponse

from intentkit.config.config import config
from intentkit.core.agent import get_agent
from intentkit.models.agent_data import AgentData
from intentkit.utils.error import IntentKitAPIError

from app.services.twitter.oauth2 import oauth2_user_handler

twitter_callback_router = APIRouter(prefix="/callback/auth", tags=["Callback"])


def is_valid_url(url: str) -> bool:
    """Check if a URL is valid.

    Args:
        url: URL to validate

    Returns:
        bool: True if URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except (ValueError, AttributeError, TypeError):
        return False


@twitter_callback_router.get("/twitter")
async def twitter_oauth_callback(
    state: str,
    code: str | None = None,
    error: str | None = None,
):
    """Handle Twitter OAuth2 callback.

    This endpoint is called by Twitter after the user authorizes the application.
    It exchanges the authorization code for access and refresh tokens, then stores
    them in the database.

    **Query Parameters:**
    * `state` - URL-encoded state containing agent_id and redirect_uri
    * `code` - Authorization code from Twitter
    * `error` - Error message from Twitter (optional)

    **Returns:**
    * JSONResponse or RedirectResponse depending on redirect_uri
    """
    if not state:
        raise IntentKitAPIError(
            status_code=400,
            key="MissingStateParameter",
            message="Missing state parameter",
        )

    redirect_uri = ""
    try:
        # Parse state parameter
        state_params = parse_qs(state)
        agent_id = state_params.get("agent_id", [""])[0]
        redirect_uri = state_params.get("redirect_uri", [""])[0]

        if error:
            raise IntentKitAPIError(
                status_code=400, key="TwitterAuthError", message=error
            )

        if not code:
            raise IntentKitAPIError(
                status_code=400,
                key="MissingCodeParameter",
                message="Missing code parameter",
            )

        if not agent_id:
            raise IntentKitAPIError(
                status_code=400,
                key="MissingAgentId",
                message="Missing agent_id in state parameter",
            )

        agent = await get_agent(agent_id)
        if not agent:
            raise IntentKitAPIError(
                status_code=404,
                key="AgentNotFound",
                message=f"Agent {agent_id} not found",
            )

        agent_data = await AgentData.get(agent_id)

        # Exchange code for tokens
        authorization_response = (
            f"{config.twitter_oauth2_redirect_uri}?state={state}&code={code}"
        )
        token = oauth2_user_handler.get_token(authorization_response)

        # Store tokens in database
        agent_data.twitter_access_token = token["access_token"]
        agent_data.twitter_refresh_token = token["refresh_token"]
        agent_data.twitter_access_token_expires_at = datetime.fromtimestamp(
            token["expires_at"], tz=UTC
        )

        # Get user info
        # Get user info
        client = tweepy.Client(
            bearer_token=token["access_token"], return_type=cast(Any, dict)
        )
        me: dict[str, Any] | Any = client.get_me(
            user_auth=False,
            user_fields="id,username,name,verified",
        )

        username = None
        if me and "data" in me:
            data = me["data"]
            agent_data.twitter_id = data.get("id")
            username = data.get("username")
            agent_data.twitter_username = username
            agent_data.twitter_name = data.get("name")
            agent_data.twitter_is_verified = data.get("verified")

        # Commit changes
        await agent_data.save()

        # Handle response based on redirect_uri
        if redirect_uri and is_valid_url(redirect_uri):
            params = {"twitter_auth": "success", "username": username}
            redirect_url = f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}{urlencode(params)}"
            return RedirectResponse(url=redirect_url)
        else:
            return JSONResponse(
                content={
                    "message": "Authentication successful, you can close this window",
                    "username": username,
                },
                status_code=200,
            )
    except IntentKitAPIError as http_exc:
        # Handle error response
        if redirect_uri and is_valid_url(redirect_uri):
            params = {"twitter_auth": "failed", "error": str(http_exc.message)}
            redirect_url = f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}{urlencode(params)}"
            return RedirectResponse(url=redirect_url)
        # Re-raise HTTP exceptions to preserve their status codes
        raise http_exc
    except Exception as e:
        # Handle error response for unexpected errors
        if redirect_uri and is_valid_url(redirect_uri):
            params = {"twitter_auth": "failed", "error": str(e)}
            redirect_url = f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}{urlencode(params)}"
            return RedirectResponse(url=redirect_url)
        # For unexpected errors, use 500 status code
        raise IntentKitAPIError(status_code=500, key="UnexpectedError", message=str(e))
