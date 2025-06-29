import datetime
import time
from typing import Type

import httpx
from langchain.tools.base import ToolException
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, HttpUrl

from .base import ElfaBaseTool, base_url


def get_current_epoch_timestamp() -> int:
    """Returns the current epoch timestamp (seconds since 1970-01-01 UTC)."""
    return int(time.time())


def get_yesterday_epoch_timestamp() -> int:
    """Returns the epoch timestamp for yesterday (beginning of yesterday in UTC)."""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    # Combine with midnight time to get beginning of yesterday
    yesterday_midnight = datetime.datetime.combine(yesterday, datetime.time.min)
    # Convert to UTC
    yesterday_midnight_utc = yesterday_midnight.replace(tzinfo=datetime.timezone.utc)
    return int(yesterday_midnight_utc.timestamp())


class ElfaGetMentionsInput(BaseModel):
    pass


class MediaUrl(BaseModel):
    url: str | None = Field(None, description="Media URL")
    type: str | None = Field(None, description="Media type")


class AccountData(BaseModel):
    name: str | None = Field(None, description="the name of the account")
    location: str | None = Field(
        None, description="the geographical location of the user account"
    )
    userSince: str | None = Field(None, description="account registration date")
    description: str | None = Field(None, description="description of the account")
    profileImageUrl: str | None = Field(None, description="url of the profile image")
    profileBannerUrl: str | None = Field(
        None, description="the url of the user profile banner"
    )


class Account(BaseModel):
    id: int | None = Field(None, description="id of the account")
    username: str | None = Field(None, description="username of the account")
    data: AccountData | None = Field(
        None, description="detailed information of the account"
    )
    followerCount: int | None = Field(
        None, description="the total number of the followers"
    )
    followingCount: int | None = Field(
        None, description="the total number of the followings"
    )
    isVerified: bool | None = Field(
        None, description="whether is a verified account of Twitter or not"
    )


class TweetData(BaseModel):
    mediaUrls: list[MediaUrl] | None = Field(
        None, description="the URLs of the media files"
    )


class Tweet(BaseModel):
    id: str | None = Field(None, description="Tweet ID")
    type: str | None = Field(None, description="Tweet type")
    content: str | None = Field(None, description="content of the Tweet")
    originalUrl: str | None = Field(None, description="the original URL of the tweet")
    data: TweetData | None = Field(None, description="the data of the Tweet")
    likeCount: int | None = Field(None, description="number of times liked")
    quoteCount: int | None = Field(None, description="content of the quoted")
    replyCount: int | None = Field(None, description="number of times replied")
    repostCount: int | None = Field(None, description="number of the reposts")
    viewCount: int | None = Field(None, description="number of views")
    mentionedAt: str | None = Field(
        None, description="the time of getting mentioned by other accounts"
    )
    bookmarkCount: int | None = Field(None, description="number of times bookmarked")
    account: Account | None = Field(None, description="the account information")
    repliedToUser: str | None = Field(None, description="replied to user")
    repliedToTweet: str | None = Field(None, description="replied to tweet")


class ElfaGetMentionsOutput(BaseModel):
    success: bool
    data: list[Tweet] | None = Field(None, description="the list of tweets.")


class ElfaGetMentions(ElfaBaseTool):
    """
    This tool uses the Elfa AI API to query hourly-updated tweets from "smart accounts" – accounts identified as influential or relevant – that have received at least 10 interactions (comments, retweets, quote tweets).

    This tool is useful for:

    * **Real-time Trend Analysis:**  Identify emerging trends and discussions as they happen.
    * **Competitor Monitoring:** Track the social media activity of your competitors.
    * **Influencer Tracking:** Monitor the conversations and content shared by key influencers.
    * **Reputation Management:**  Identify and address potential PR issues.

    The data returned includes the tweet content, timestamp, and potentially other relevant metadata.

    Attributes:
        name (str): Name of the tool, specifically "elfa_get_mentions".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "elfa_get_mentions"
    description: str = """This tool uses the Elfa AI API to query hourly-updated tweets from "smart accounts" – accounts identified as influential or relevant – that have received at least 10 interactions (comments, retweets, quote tweets).

        This tool is useful for:

        * **Real-time Trend Analysis:**  Identify emerging trends and discussions as they happen.
        * **Competitor Monitoring:** Track the social media activity of your competitors.
        * **Influencer Tracking:** Monitor the conversations and content shared by key influencers.
        * **Reputation Management:**  Identify and address potential PR issues.

        The data returned includes the tweet content, timestamp, and potentially other relevant metadata."""
    args_schema: Type[BaseModel] = ElfaGetMentionsInput

    async def _arun(
        self, config: RunnableConfig = None, **kwargs
    ) -> ElfaGetMentionsOutput:
        """Run the tool to get the the ELFA AI API to query hourly-updated tweets from smart accounts with at least 10 interactions (comments, retweets, quote tweets).

        Args:
            config: The configuration for the runnable, containing agent context.
            **kwargs: Additional parameters.

        Returns:
            ElfaGetMentionsOutput: A structured output containing output of Elfa get mentions API.

        Raises:
            Exception: If there's an error accessing the Elfa API.
        """
        context = self.context_from_config(config)
        api_key = self.get_api_key(context)
        if not api_key:
            raise ValueError("Elfa API key not found")

        url = f"{base_url}/v1/mentions"
        headers = {
            "accept": "application/json",
            "x-elfa-api-key": api_key,
        }

        params = ElfaGetMentionsInput(limit=100, offset=0).model_dump(exclude_none=True)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, headers=headers, timeout=30, params=params
                )
                response.raise_for_status()
                json_dict = response.json()

                res = ElfaGetMentionsOutput(**json_dict)

                return res
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Elfa API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Elfa API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"error from Elfa API: {e}") from e


class ElfaGetTopMentionsInput(BaseModel):
    ticker: str = Field(description="Stock ticker symbol (e.g., ETH, $ETH, BTC, $BTC)")
    timeWindow: str | None = Field("24h", description="Time window (e.g., 24h, 7d)")
    includeAccountDetails: bool | None = Field(
        False, description="Include account details"
    )


class TopMentionsPostMetrics(BaseModel):
    like_count: int | None = Field(None, description="Number of likes for the post")
    reply_count: int | None = Field(None, description="Number of replies for the post")
    repost_count: int | None = Field(None, description="Number of reposts for the post")
    view_count: int | None = Field(None, description="Number of views for the post")


class TwitterAccountInfo(BaseModel):
    username: str | None = Field(None, description="Twitter username")
    twitter_user_id: str | None = Field(None, description="Twitter user ID")
    description: str | None = Field(None, description="Twitter account description")
    profileImageUrl: HttpUrl | None = Field(
        None, description="URL of the profile image"
    )


class TopMentionsPostData(BaseModel):
    id: int | None = Field(None, description="Unique ID of the post")
    twitter_id: str | None = Field(None, description="Twitter ID of the post")
    twitter_user_id: str | None = Field(
        None, description="Twitter user ID of the poster"
    )
    content: str | None = Field(None, description="Content of the post")
    mentioned_at: str | None = Field(
        None, description="Timestamp when the post was mentioned"
    )  # Consider using datetime if needed
    type: str | None = Field(None, description="Type of the post (e.g., post, quote)")
    metrics: TopMentionsPostMetrics | None = Field(
        None, description="Metrics related to the post"
    )
    twitter_account_info: TwitterAccountInfo | None = Field(
        None, description="Information about the Twitter account"
    )


class TopMentionsData(BaseModel):
    data: list[TopMentionsPostData] | None = Field(
        None, description="List of post data"
    )
    total: int | None = Field(None, description="Total number of posts")
    page: int | None = Field(None, description="Current page number")
    pageSize: int | None = Field(None, description="Number of posts per page")


class ElfaGetTopMentionsOutput(BaseModel):
    success: bool = Field(None, description="Indicates if the request was successful")
    data: TopMentionsData | None = Field(None, description="Data returned by the API")


class ElfaGetTopMentions(ElfaBaseTool):
    """
    This tool uses the Elfa API to query tweets mentioning a specific stock ticker. The tweets are ranked by view count, providing insight into the most visible and potentially influential discussions surrounding the stock. The results are updated hourly, allowing for real-time monitoring of market sentiment.

    This tool is useful for:

    * **Real-time Sentiment Analysis:** Track changes in public opinion about a stock.
    * **News Monitoring:** Identify trending news and discussions related to a specific ticker.
    * **Investor Insights:** Monitor the conversations and opinions of investors and traders.

    To use this tool, simply provide the stock ticker symbol (e.g., "AAPL", "TSLA"). The tool will return a list of tweets, ranked by view count.

    Attributes:
        name (str): Name of the tool, specifically "elfa_get_top_mentions".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "elfa_get_top_mentions"
    description: str = """This tool uses the Elfa API to query tweets mentioning a specific stock ticker. The tweets are ranked by view count, providing insight into the most visible and potentially influential discussions surrounding the stock. The results are updated hourly, allowing for real-time monitoring of market sentiment.

        This tool is useful for:

        * **Real-time Sentiment Analysis:** Track changes in public opinion about a stock.
        * **News Monitoring:** Identify trending news and discussions related to a specific ticker.
        * **Investor Insights:** Monitor the conversations and opinions of investors and traders.

        To use this tool, simply provide the stock ticker symbol (e.g., "AAPL", "TSLA"). The tool will return a list of tweets, ranked by view count."""
    args_schema: Type[BaseModel] = ElfaGetTopMentionsInput

    def _run(
        self,
        ticker: str,
        timeWindow: str = "24h",
        includeAccountDetails: bool = False,
    ) -> ElfaGetTopMentionsOutput:
        """Run the tool to get the Elfa API to query tweets mentioning a specific stock ticker. The tweets are ranked by view count and the results are updated hourly.

        Returns:
             ElfaAskOutput: A structured output containing output of Elfa top mentions API.

        Raises:
            Exception: If there's an error accessing the Elfa API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(
        self,
        ticker: str,
        timeWindow: str = "24h",
        includeAccountDetails: bool = False,
        config: RunnableConfig = None,
        **kwargs,
    ) -> ElfaGetTopMentionsOutput:
        """Run the tool to get the Elfa API to query tweets mentioning a specific stock ticker. The tweets are ranked by view count and the results are updated hourly.

        Args:
            ticker: Stock ticker symbol.
            timeWindow: Time window (optional).
            includeAccountDetails: Include account details.
            config: The configuration for the runnable, containing agent context.
            **kwargs: Additional parameters.

        Returns:
            ElfaGetTopMentionsOutput: A structured output containing output of Elfa top mentions API.

        Raises:
            Exception: If there's an error accessing the Elfa API.
        """
        context = self.context_from_config(config)
        api_key = self.get_api_key(context)
        if not api_key:
            raise ValueError("Elfa API key not found")

        url = f"{base_url}/v1/top-mentions"
        headers = {
            "accept": "application/json",
            "x-elfa-api-key": api_key,
        }

        params = ElfaGetTopMentionsInput(
            ticker=ticker,
            timeWindow=timeWindow,
            page=1,
            pageSize=20,
            includeAccountDetails=includeAccountDetails,
        ).model_dump(exclude_none=True)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, headers=headers, timeout=30, params=params
                )
                response.raise_for_status()
                json_dict = response.json()

                res = ElfaGetTopMentionsOutput(**json_dict)

                return res
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Elfa API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Elfa API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"error from Elfa API: {e}") from e


class ElfaSearchMentionsInput(BaseModel):
    keywords: str = Field(
        description="Up to 5 keywords to search for, separated by commas. Phrases accepted"
    )
    from_: int | None = Field(
        None, description="Start date (unix timestamp), set default as 24 hours ago"
    )
    to: int | None = Field(
        None, description="End date (unix timestamp), set default as now"
    )


class SearchMentionsPostMetrics(BaseModel):
    like_count: int | None = Field(None, description="Number of likes for the post")
    reply_count: int | None = Field(None, description="Number of replies for the post")
    repost_count: int | None = Field(None, description="Number of reposts for the post")
    view_count: int | None = Field(None, description="Number of views for the post")


class SearchMentionsPostData(BaseModel):
    id: int | None = Field(None, description="Unique ID of the post")
    twitter_id: str | None = Field(None, description="Twitter ID of the post")
    twitter_user_id: str | None = Field(
        None, description="Twitter user ID of the poster"
    )
    content: str | None = Field(None, description="Content of the post")
    mentioned_at: str | None = Field(
        None, description="Timestamp when the post was mentioned"
    )
    type: str | None = Field(
        None, description="Type of the post (e.g., post, quote, repost)"
    )
    metrics: SearchMentionsPostMetrics | None = Field(
        None, description="Metrics related to the post"
    )
    sentiment: str | None = Field(
        None, description="Sentiment of the post (e.g., positive, negative, neutral)"
    )


class ElfaSearchMentionsOutput(BaseModel):
    success: bool | None
    data: list[SearchMentionsPostData] | None = Field(
        None, description="the list of tweets."
    )


class ElfaSearchMentions(ElfaBaseTool):
    """
    This tool uses the Elfa API to search tweets mentioning up to five keywords.  It can search within the past 30 days of data, which is updated every 5 minutes, or access up to six months of historical tweet data.

    This tool is useful for:

    * **Market Research:**  Track conversations and sentiment around specific products or industries.
    * **Brand Monitoring:** Monitor mentions of your brand and identify potential PR issues.
    * **Public Opinion Tracking:** Analyze public opinion on various topics.
    * **Competitive Analysis:**  See what people are saying about your competitors.

    To use this tool, provide up to five keywords.  You can also specify whether you want to search recent or historical tweets.

    Attributes:
        name (str): Name of the tool, specifically "elfa_search_mentions".
        description (str): Comprehensive description of the tool's purpose and functionality.
        args_schema (Type[BaseModel]): Schema for input arguments, specifying expected parameters.
    """

    name: str = "elfa_search_mentions"
    description: str = """This tool uses the Elfa API to search tweets mentioning up to five keywords.  It can search within the past 30 days of data, which is updated every 5 minutes, or access up to six months of historical tweet data.

        This tool is useful for:

        * **Market Research:**  Track conversations and sentiment around specific products or industries.
        * **Brand Monitoring:** Monitor mentions of your brand and identify potential PR issues.
        * **Public Opinion Tracking:** Analyze public opinion on various topics.
        * **Competitive Analysis:**  See what people are saying about your competitors.

        To use this tool, provide up to five keywords.  You can also specify whether you want to search recent or historical tweets."""
    args_schema: Type[BaseModel] = ElfaSearchMentionsInput

    def _run(
        self,
        keywords: str,
        from_: int = get_current_epoch_timestamp(),
        to: int = get_yesterday_epoch_timestamp(),
    ) -> ElfaSearchMentionsOutput:
        """Run the tool to for tweets mentioning up to five keywords within the past 30 days.  It can access up to six months of historical tweet data, updated every five minutes via the Elfa API.

        Returns:
             ElfaAskOutput: A structured output containing output of Elfa top mentions API.

        Raises:
            Exception: If there's an error accessing the Elfa API.
        """
        raise NotImplementedError("Use _arun instead")

    async def _arun(
        self,
        keywords: str,
        from_: int = get_current_epoch_timestamp(),
        to: int = get_yesterday_epoch_timestamp(),
        config: RunnableConfig = None,
        **kwargs,
    ) -> ElfaSearchMentionsOutput:
        """Run the tool to for tweets mentioning up to five keywords within the past 30 days.  It can access up to six months of historical tweet data, updated every five minutes via the Elfa API.

        Args:
            keywords: Keywords to search.
            from_: Start date (Unix timestamp).
            to: End date (Unix timestamp).
            config: The configuration for the runnable, containing agent context.
            **kwargs: Additional parameters.

        Returns:
            ElfaSearchMentionsOutput: A structured output containing output of Elfa top mentions API.

        Raises:
            Exception: If there's an error accessing the Elfa API.
        """
        context = self.context_from_config(config)
        api_key = self.get_api_key(context)
        if not api_key:
            raise ValueError("Elfa API key not found")

        url = f"{base_url}/v1/mentions/search"
        headers = {
            "accept": "application/json",
            "x-elfa-api-key": api_key,
        }

        params = ElfaSearchMentionsInput(
            keywords=keywords,
            from_=from_,
            to=to,
        ).model_dump(exclude_none=True)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, headers=headers, timeout=30, params=params
                )
                response.raise_for_status()
                json_dict = response.json()

                res = ElfaSearchMentionsOutput(**json_dict)

                return res
            except httpx.RequestError as req_err:
                raise ToolException(
                    f"request error from Elfa API: {req_err}"
                ) from req_err
            except httpx.HTTPStatusError as http_err:
                raise ToolException(
                    f"http error from Elfa API: {http_err}"
                ) from http_err
            except Exception as e:
                raise ToolException(f"error from Elfa API: {e}") from e
