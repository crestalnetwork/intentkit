from typing import Type

from pydantic import BaseModel, Field

from skills.twitter.base import TwitterBaseTool


class TwitterPostTweetInput(BaseModel):
    """Input for TwitterPostTweet tool."""

    text: str = Field(
        description="The text content of the tweet to post", max_length=280
    )


class TwitterPostTweet(TwitterBaseTool):
    """Tool for posting tweets to Twitter.

    This tool uses the Twitter API v2 to post new tweets to Twitter.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "twitter_post_tweet"
    description: str = "Post a new tweet to Twitter"
    args_schema: Type[BaseModel] = TwitterPostTweetInput

    def _run(self, text: str) -> str:
        """Run the tool to post a tweet.

        Args:
            text (str): The text content of the tweet to post.

        Returns:
            str: A message indicating success or failure of the tweet posting.

        Raises:
            Exception: If there's an error posting to the Twitter API.
        """
        try:
            # Check rate limit only when not using OAuth
            if not self.twitter.use_key:
                is_rate_limited, error = self.check_rate_limit(
                    max_requests=24, interval=1440
                )
                if is_rate_limited:
                    return f"Error posting tweet: {error}"

            client = self.twitter.get_client()
            if not client:
                return "Failed to get Twitter client. Please check your authentication."

            # Post tweet using tweepy client
            response = client.create_tweet(text=text, user_auth=self.twitter.use_key)

            if "data" in response and "id" in response["data"]:
                tweet_id = response["data"]["id"]
                return f"Tweet posted successfully! Tweet ID: {tweet_id}"
            return "Failed to post tweet."

        except Exception as e:
            return f"Error posting tweet: {str(e)}"

    async def _arun(self, text: str) -> str:
        """Async implementation of the tool.

        This tool doesn't have a native async implementation, so we call the sync version.
        """
        return self._run(text=text)
