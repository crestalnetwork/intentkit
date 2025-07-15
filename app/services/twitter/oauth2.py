"""Twitter OAuth2 authentication module."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import verify_admin_jwt
from intentkit.clients.twitter import OAuth2UserHandler
from intentkit.config.config import config

# Initialize Twitter OAuth2 client
oauth2_user_handler = OAuth2UserHandler(
    client_id=config.twitter_oauth2_client_id,
    client_secret=config.twitter_oauth2_client_secret,
    # backend uri point to twitter_oauth_callback
    redirect_uri=config.twitter_oauth2_redirect_uri,
    scope=[
        "tweet.read",
        "tweet.write",
        "users.read",
        "offline.access",
        "follows.read",
        "follows.write",
        "like.read",
        "like.write",
        "media.write",
    ],
)


class TwitterAuthResponse(BaseModel):
    agent_id: str
    url: str


router = APIRouter(tags=["Auth"])


@router.get(
    "/auth/twitter",
    response_model=TwitterAuthResponse,
    dependencies=[Depends(verify_admin_jwt)],
)
async def get_twitter_auth_url(agent_id: str, redirect_uri: str) -> TwitterAuthResponse:
    """Get Twitter OAuth2 authorization URL.

    **Query Parameters:**
    * `agent_id` - ID of the agent to authenticate
    * `redirect_uri` - DApp URI to redirect to after authorization from agentkit to DApp

    **Returns:**
    * Object containing agent_id and authorization URL
    """
    url = oauth2_user_handler.get_authorization_url(agent_id, redirect_uri)
    return TwitterAuthResponse(agent_id=agent_id, url=url)


def get_authorization_url(agent_id: str, redirect_uri: str) -> str:
    """Get Twitter OAuth2 authorization URL.

    **Query Parameters:**
    * `agent_id` - ID of the agent to authenticate
    * `redirect_uri` - DApp URI to redirect to after authorization from agentkit to DApp

    **Returns:**
    * Authorization URL with agent_id as state parameter
    """
    return oauth2_user_handler.get_authorization_url(agent_id, redirect_uri)
