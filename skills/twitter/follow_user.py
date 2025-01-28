from typing import Type

from pydantic import BaseModel, Field

from skills.twitter.base import TwitterBaseTool


class TwitterFollowUserInput(BaseModel):
    """Input for TwitterFollowUser tool."""

    user_id: str = Field(description="The ID of the user to follow")


class TwitterFollowUserOutput(BaseModel):
    """Output for TwitterFollowUser tool."""

    success: bool
    message: str


class TwitterFollowUser(TwitterBaseTool):
    """Tool for following a Twitter user.

    This tool uses the Twitter API v2 to follow a user on Twitter.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "twitter_follow_user"
    description: str = "Follow a Twitter user"
    args_schema: Type[BaseModel] = TwitterFollowUserInput

    def _run(self, user_id: str) -> TwitterFollowUserOutput:
        """Run the tool to follow a user.

        Args:
            user_id (str): The ID of the user to follow.

        Returns:
            TwitterFollowUserOutput: A structured output containing the result of the follow action.

        Raises:
            Exception: If there's an error accessing the Twitter API.
        """
        try:
            # Check rate limit only when not using OAuth
            if not self.twitter.use_key:
                is_rate_limited, error = self.check_rate_limit(
                    max_requests=5, interval=15
                )
                if is_rate_limited:
                    return TwitterFollowUserOutput(
                        success=False,
                        message=self._get_error_with_username(
                            f"Error following user: {error}"
                        ),
                    )

            client = self.twitter.get_client()
            if not client:
                return TwitterFollowUserOutput(
                    success=False,
                    message=self._get_error_with_username(
                        "Failed to get Twitter client. Please check your authentication."
                    ),
                )

            # Follow the user using tweepy client
            response = client.follow_user(
                target_user_id=user_id, user_auth=self.twitter.use_key
            )

            if "data" in response and response["data"].get("following"):
                return TwitterFollowUserOutput(
                    success=True, message=f"Successfully followed user {user_id}"
                )
            return TwitterFollowUserOutput(
                success=False,
                message=self._get_error_with_username("Failed to follow user."),
            )

        except Exception as e:
            return TwitterFollowUserOutput(
                success=False, message=self._get_error_with_username(str(e))
            )

    async def _arun(self, user_id: str) -> TwitterFollowUserOutput:
        """Async implementation of the tool.

        This tool doesn't have a native async implementation, so we call the sync version.
        """
        return self._run(user_id=user_id)
