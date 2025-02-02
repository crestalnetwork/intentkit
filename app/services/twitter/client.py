import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from tweepy import Client

from abstracts.agent import AgentStoreABC
from abstracts.twitter import TwitterABC
from models.agent import AgentData

logger = logging.getLogger(__name__)


class TwitterClient(TwitterABC):
    """Implementation of Twitter operations using Tweepy client.

    This class provides concrete implementations for interacting with Twitter's API
    through a Tweepy client, supporting both API key and OAuth2 authentication.

    Args:
        agent_store: The agent store for persisting data
        config: Configuration dictionary that may contain API keys
    """

    def __init__(self, agent_store: AgentStoreABC, config: Dict) -> None:
        """Initialize the Twitter client.

        Args:
            agent_store: The agent store for persisting data
            config: Configuration dictionary that may contain API keys
        """
        self._client: Optional[Client] = None
        self._agent_store = agent_store
        self._agent_data: Optional[AgentData] = self._agent_store.get_data()
        self.use_key = False
        self.need_auth = False

        # Check if we have API keys in config
        if all(
            key in config and config[key]
            for key in [
                "consumer_key",
                "consumer_secret",
                "access_token",
                "access_token_secret",
            ]
        ):
            self._client = Client(
                consumer_key=config["consumer_key"],
                consumer_secret=config["consumer_secret"],
                access_token=config["access_token"],
                access_token_secret=config["access_token_secret"],
                return_type=dict,
            )
            self.use_key = True
        else:
            # Try to get OAuth2 token from agent data
            if self._agent_data and self._agent_data.twitter_access_token:
                # Check if token is expired
                if (
                    self._agent_data.twitter_access_token_expires_at
                    and self._agent_data.twitter_access_token_expires_at
                    > datetime.now(timezone.utc)
                ):
                    self._client = Client(
                        bearer_token=self._agent_data.twitter_access_token,
                        return_type=dict,
                    )
                    self.use_key = False
                else:
                    self.need_auth = True
            else:
                self.need_auth = True
        # Everytime we get a client, we need to refresh the user data
        if not self.need_auth:
            me = self._client.get_me(user_auth=self.use_key)
            if me and "data" in me and "id" in me["data"]:
                self._agent_store.set_data(
                    {
                        "twitter_id": me["data"]["id"],
                        "twitter_username": me["data"]["username"],
                        "twitter_name": me["data"]["name"],
                    }
                )
            self._agent_data = self._agent_store.get_data()
            logger.info(
                f"Twitter client initialized. "
                f"Use API key: {self.use_key}, "
                f"User ID: {self.get_id()}, "
                f"Username: {self.get_username()}, "
                f"Name: {self.get_name()}"
            )

    def get_client(self) -> Optional[Client]:
        """Get a configured Tweepy client.

        If using OAuth2 authentication, this method will check token expiration and
        attempt to refresh the client with new agent data if needed.

        Returns:
            A configured Tweepy client if credentials are valid, None otherwise
        """
        # For API key auth, just return the client
        if self.use_key:
            return self._client

        # For OAuth2, check token expiration
        if (
            self._agent_data
            and self._agent_data.twitter_access_token_expires_at
            and self._agent_data.twitter_access_token_expires_at
            <= datetime.now(timezone.utc)
        ):
            # Token expired, try to get fresh agent data
            self._agent_data = self._agent_store.get_data()

            # Check if new token is valid
            if (
                self._agent_data
                and self._agent_data.twitter_access_token
                and self._agent_data.twitter_access_token_expires_at
                and self._agent_data.twitter_access_token_expires_at
                > datetime.now(timezone.utc)
            ):
                # Create new client with fresh token
                self._client = Client(
                    bearer_token=self._agent_data.twitter_access_token,
                    return_type=dict,
                )
            else:
                # No valid token available
                self._client = None
                self.need_auth = True

        return self._client

    def get_id(self) -> Optional[str]:
        """Get the Twitter user ID.

        Returns:
            The Twitter user ID if available, None otherwise
        """
        if not self._client:
            return None

        # For OAuth2, use cached agent data
        if not self.use_key and self._agent_data and self._agent_data.twitter_id:
            return self._agent_data.twitter_id

        try:
            # Try to get from Twitter API
            me = self._client.get_me()
            if me and "data" in me and "id" in me["data"]:
                return me["data"]["id"]
        except Exception:
            pass
        return None

    def get_username(self) -> Optional[str]:
        """Get the Twitter username.

        Returns:
            The Twitter username (without @ symbol) if available, None otherwise
        """
        if not self._client:
            return None

        # For OAuth2, use cached agent data
        if not self.use_key and self._agent_data and self._agent_data.twitter_username:
            return self._agent_data.twitter_username

        try:
            # Try to get from Twitter API
            me = self._client.get_me()
            if me and "data" in me and "username" in me["data"]:
                return me["data"]["username"]
        except Exception:
            pass
        return None

    def get_name(self) -> Optional[str]:
        """Get the Twitter display name.

        Returns:
            The Twitter display name if available, None otherwise
        """
        if not self._client:
            return None

        # For OAuth2, use cached agent data
        if not self.use_key and self._agent_data and self._agent_data.twitter_name:
            return self._agent_data.twitter_name

        try:
            # Try to get from Twitter API
            me = self._client.get_me()
            if me and "data" in me and "name" in me["data"]:
                return me["data"]["name"]
        except Exception:
            pass
        return None
