from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Type

from pydantic import BaseModel, Field

from abstracts.agent import AgentStoreABC
from abstracts.skill import IntentKitSkill, SkillStoreABC
from abstracts.twitter import TwitterABC


class TwitterBaseTool(IntentKitSkill):
    """Base class for Twitter tools."""

    twitter: TwitterABC = Field(description="The Twitter client abstraction")
    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    agent_id: str = Field(description="The ID of the agent")
    agent_store: AgentStoreABC = Field(
        description="The agent store for persisting data"
    )
    store: SkillStoreABC = Field(description="The skill store for persisting data")

    def _get_error_with_username(self, error_msg: str) -> str:
        """Get error message with username if available.

        Args:
            error_msg: The original error message.

        Returns:
            Error message with username if available.
        """
        username = self.twitter.get_username()
        if username:
            return f"Error for Twitter user @{username}: {error_msg}"
        return error_msg

    def check_rate_limit(
        self, max_requests: int = 1, interval: int = 15
    ) -> tuple[bool, str | None]:
        """Check if the rate limit has been exceeded.

        Args:
            max_requests: Maximum number of requests allowed within the rate limit window.
            interval: Time interval in minutes for the rate limit window.

        Returns:
            tuple[bool, str | None]: (is_rate_limited, error_message)
        """
        rate_limit = self.store.get_agent_skill_data(
            self.agent_id, self.name, "rate_limit"
        )

        current_time = datetime.now(tz=timezone.utc)

        if (
            rate_limit
            and rate_limit.get("reset_time")
            and rate_limit["count"] is not None
            and datetime.fromisoformat(rate_limit["reset_time"]) > current_time
        ):
            if rate_limit["count"] >= max_requests:
                return True, "Rate limit exceeded"
            else:
                rate_limit["count"] += 1
                self.store.save_agent_skill_data(
                    self.agent_id, self.name, "rate_limit", rate_limit
                )
                return False, None

        # If no rate limit exists or it has expired, create a new one
        new_rate_limit = {
            "count": 1,
            "reset_time": (current_time + timedelta(minutes=interval)).isoformat(),
        }
        self.store.save_agent_skill_data(
            self.agent_id, self.name, "rate_limit", new_rate_limit
        )
        return False, None

    def process_tweets_response(self, response: Dict[str, Any]) -> List["Tweet"]:
        """Process Twitter API response and convert it to a list of Tweet objects.

        Args:
            response: Raw Twitter API response containing tweets data and includes.

        Returns:
            List[Tweet]: List of processed Tweet objects.
        """
        result = []
        if not response.get("data"):
            return result

        # Create lookup dictionaries from includes
        users_dict = {}
        if response.get("includes") and "users" in response.get("includes"):
            users_dict = {
                user["id"]: TwitterUser(
                    id=str(user["id"]),
                    name=user["name"],
                    username=user["username"],
                    description=user["description"],
                    public_metrics=user["public_metrics"],
                    is_following="following" in user.get("connection_status", []),
                    is_follower="followed_by" in user.get("connection_status", []),
                )
                for user in response.get("includes", {}).get("users", [])
            }

        media_dict = {}
        if response.get("includes") and "media" in response.get("includes"):
            media_dict = {
                media["media_key"]: TwitterMedia(
                    media_key=media["media_key"],
                    type=media["type"],
                    url=media.get("url"),
                )
                for media in response.get("includes", {}).get("media", [])
            }

        tweets_dict = {}
        if response.get("includes") and "tweets" in response.get("includes"):
            tweets_dict = {
                tweet["id"]: Tweet(
                    id=str(tweet["id"]),
                    text=tweet["text"],
                    author_id=str(tweet["author_id"]),
                    created_at=datetime.fromisoformat(
                        tweet["created_at"].replace("Z", "+00:00")
                    ),
                    author=users_dict.get(tweet["author_id"]),
                    referenced_tweets=None,  # Will be populated in second pass
                    attachments=None,
                )
                for tweet in response.get("includes", {}).get("tweets", [])
            }

        # Create main tweet objects
        for tweet_data in response.get("data", []):
            try:
                # Create list of media attachments if present
                media_list = []
                if (
                    "attachments" in tweet_data
                    and "media_keys" in tweet_data["attachments"]
                ):
                    media_list = [
                        media_dict[media_key]
                        for media_key in tweet_data["attachments"]["media_keys"]
                        if media_key in media_dict
                    ]

                # Create list of referenced tweets if present
                ref_tweets = []
                if "referenced_tweets" in tweet_data:
                    ref_tweets = [
                        tweets_dict[ref_tweet["id"]]
                        for ref_tweet in tweet_data["referenced_tweets"]
                        if ref_tweet["id"] in tweets_dict
                    ]

                tweet_obj = Tweet(
                    id=str(tweet_data["id"]),
                    text=tweet_data["text"],
                    author_id=str(tweet_data["author_id"]),
                    author=users_dict.get(tweet_data["author_id"]),
                    created_at=datetime.fromisoformat(
                        tweet_data["created_at"].replace("Z", "+00:00")
                    ),
                    referenced_tweets=ref_tweets if ref_tweets else None,
                    attachments=media_list if media_list else None,
                )
                result.append(tweet_obj)
            except Exception as e:
                raise Exception(f"Error processing tweet {tweet_data}: {str(e)}")

        return result


class TwitterMedia(BaseModel):
    """Model representing Twitter media from the API response."""

    media_key: str
    type: str
    url: str | None = None


class TwitterUser(BaseModel):
    """Model representing a Twitter user from the API response."""

    id: str
    name: str
    username: str
    description: str
    public_metrics: dict = Field(
        description="User metrics including followers_count, following_count, tweet_count, listed_count, like_count, and media_count"
    )
    is_following: bool = Field(
        description="Whether the authenticated user is following this user",
        default=False,
    )
    is_follower: bool = Field(
        description="Whether this user is following the authenticated user",
        default=False,
    )


class Tweet(BaseModel):
    """Model representing a Twitter tweet."""

    id: str
    text: str
    author_id: str
    author: TwitterUser | None = None
    created_at: datetime
    referenced_tweets: list["Tweet"] | None = None
    attachments: list[TwitterMedia] | None = None
