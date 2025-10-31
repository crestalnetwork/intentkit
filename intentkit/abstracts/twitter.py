from abc import ABC, abstractmethod

from tweepy.asynchronous import AsyncClient


class TwitterABC(ABC):
    """Abstract base class for Twitter operations.

    This class defines the interface for interacting with Twitter's API
    through a Tweepy client.
    """

    agent_id: str
    use_key = False

    @abstractmethod
    async def get_client(self) -> AsyncClient | None:
        """Get a configured Tweepy client.

        Returns:
            A configured Tweepy client if credentials are valid, None otherwise
        """
        pass

    @property
    @abstractmethod
    def self_id(self) -> str | None:
        """Get the Twitter user ID.

        Returns:
            The Twitter user ID if available, None otherwise
        """
        pass

    @property
    @abstractmethod
    def self_username(self) -> str | None:
        """Get the Twitter username.

        Returns:
            The Twitter username (without @ symbol) if available, None otherwise
        """
        pass

    @property
    @abstractmethod
    def self_name(self) -> str | None:
        """Get the Twitter display name.

        Returns:
            The Twitter display name if available, None otherwise
        """
        pass
