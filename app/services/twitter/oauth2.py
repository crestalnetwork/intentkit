"""Twitter OAuth2 authentication module."""

from fastapi import APIRouter
from pydantic import BaseModel
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from app.config.config import config


# this class is forked from:
# https://github.com/tweepy/tweepy/blob/main/tweepy/auth.py
# it is not maintained by the original author, bug need to be fixed
class OAuth2UserHandler(OAuth2Session):
    """OAuth 2.0 Authorization Code Flow with PKCE (User Context)
    authentication handler
    """

    def __init__(self, *, client_id, redirect_uri, scope, client_secret=None):
        super().__init__(client_id, redirect_uri=redirect_uri, scope=scope)
        if client_secret is not None:
            self.auth = HTTPBasicAuth(client_id, client_secret)
        else:
            self.auth = None
        self.code_challenge = self._client.create_code_challenge(
            self._client.create_code_verifier(128), "S256"
        )

    def get_authorization_url(self, agent_id: str):
        """Get the authorization URL to redirect the user to"""
        authorization_url, _ = self.authorization_url(
            "https://twitter.com/i/oauth2/authorize",
            state=agent_id,
            code_challenge=self.code_challenge,
            code_challenge_method="S256",
        )
        return authorization_url

    def get_token(self, authorization_response):
        """After user has authorized the app, fetch access token with
        authorization response URL
        """
        return super().fetch_token(
            "https://api.twitter.com/2/oauth2/token",
            authorization_response=authorization_response,
            auth=self.auth,
            include_client_id=True,
            code_verifier=self._client.code_verifier,
        )

    def refresh(self, refresh_token: str):
        """Refresh token"""
        return super().refresh_token(
            "https://api.twitter.com/2/oauth2/token",
            refresh_token=refresh_token,
            include_client_id=True,
        )


# Initialize Twitter OAuth2 client
oauth2_user_handler = OAuth2UserHandler(
    client_id=config.twitter_oauth2_client_id,
    client_secret=config.twitter_oauth2_client_secret,
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


@router.get("/auth/twitter", response_model=TwitterAuthResponse)
async def get_twitter_auth_url(agent_id: str) -> TwitterAuthResponse:
    """Get Twitter OAuth2 authorization URL.

    Args:
        agent_id: ID of the agent to authenticate

    Returns:
        Object containing agent_id and authorization URL
    """
    url = oauth2_user_handler.get_authorization_url(agent_id)
    return TwitterAuthResponse(agent_id=agent_id, url=url)


def get_authorization_url(agent_id: str) -> str:
    """Get Twitter OAuth2 authorization URL.

    Args:
        agent_id: ID of the agent to authenticate

    Returns:
        Authorization URL with agent_id as state parameter
    """
    return oauth2_user_handler.get_authorization_url(agent_id)
