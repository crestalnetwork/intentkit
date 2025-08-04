from enum import IntEnum
from typing import Any, Dict, List, Optional, Type, Union

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.cookiefun.base import CookieFunBaseTool, logger
from intentkit.skills.cookiefun.constants import DEFAULT_HEADERS, ENDPOINTS


class TweetType(IntEnum):
    """Tweet type for filtering."""

    Original = 0
    Reply = 1
    Quote = 2


class SortBy(IntEnum):
    """Sort options for tweets."""

    CreatedDate = 0
    Impressions = 1


class SortOrder(IntEnum):
    """Sort order options."""

    Ascending = 0
    Descending = 1


class GetAccountFeedInput(BaseModel):
    """Input for GetAccountFeed tool."""

    username: Optional[str] = Field(
        default=None,
        description="Twitter username (either username or userId is required)",
    )

    userId: Optional[str] = Field(
        default=None,
        description="Twitter user ID (either username or userId is required)",
    )

    startDate: Optional[str] = Field(
        default=None,
        description="Start date for filtering in format dd/mm/yyyy (default: 30 days ago)",
    )

    endDate: Optional[str] = Field(
        default=None,
        description="End date for filtering in format dd/mm/yyyy (default: now)",
    )

    type: Optional[int] = Field(
        default=None,
        description="Type of tweets to filter: 0 for Original, 1 for Reply, 2 for Quote (leave empty for all types)",
    )

    hasMedia: Optional[bool] = Field(
        default=None,
        description="Filter to only include tweets with media if true",
    )

    sortBy: Optional[int] = Field(
        default=None,
        description="Sort by: 0 for CreatedDate, 1 for Impressions",
    )

    sortOrder: Optional[int] = Field(
        default=None,
        description="Sort order: 0 for Ascending, 1 for Descending",
    )


class GetAccountFeed(CookieFunBaseTool):
    """Tool to get the feed (tweets) of a Twitter account."""

    name: str = "cookiefun_get_account_feed"
    description: str = "Retrieves a list of tweets for a specific Twitter account with various filtering options."
    args_schema: Type[BaseModel] = GetAccountFeedInput

    async def _arun(
        self,
        username: Optional[str] = None,
        userId: Optional[str] = None,
        startDate: Optional[str] = None,
        endDate: Optional[str] = None,
        type: Optional[int] = None,
        hasMedia: Optional[bool] = None,
        sortBy: Optional[int] = None,
        sortOrder: Optional[int] = None,
        **kwargs,
    ) -> Union[List[Dict[str, Any]], str]:
        """
        Get the feed (tweets) of a Twitter account.

        Args:
            username: Twitter username (either username or userId is required)
            userId: Twitter user ID (either username or userId is required)
            startDate: Start date for filtering in format dd/mm/yyyy (default: 30 days ago)
            endDate: End date for filtering in format dd/mm/yyyy (default: now)
            type: Type of tweets to filter (0=Original, 1=Reply, 2=Quote)
            hasMedia: Filter to only include tweets with media if true
            sortBy: Sort by field (0=CreatedDate, 1=Impressions)
            sortOrder: Sort order (0=Ascending, 1=Descending)

        Returns:
            List of tweets from the specified account matching the filter criteria.
        """
        logger.info(
            "Getting account feed for username=%s, userId=%s, startDate=%s, endDate=%s, type=%s, hasMedia=%s, sortBy=%s, sortOrder=%s",
            username,
            userId,
            startDate,
            endDate,
            type,
            hasMedia,
            sortBy,
            sortOrder,
        )

        # Validate input parameters
        if not username and not userId:
            logger.error("Neither username nor userId provided")
            return "Error: Either username or userId must be provided."

        try:
            # Get context to retrieve API key
            api_key = self.get_api_key()

            if not api_key:
                logger.error("No API key provided for CookieFun API")
                return "Error: No API key provided for CookieFun API. Please configure the API key in the agent settings."

            # Prepare request payload
            payload = {}
            if username:
                payload["username"] = username
            if userId:
                payload["userId"] = userId
            if startDate:
                payload["startDate"] = startDate
            if endDate:
                payload["endDate"] = endDate
            if type is not None:
                payload["type"] = type
            if hasMedia is not None:
                payload["hasMedia"] = hasMedia
            if sortBy is not None:
                payload["sortBy"] = sortBy
            if sortOrder is not None:
                payload["sortOrder"] = sortOrder

            # Make API request
            headers = {**DEFAULT_HEADERS, "x-api-key": api_key}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ENDPOINTS["account_feed"], headers=headers, json=payload
                )
                logger.debug(
                    "Received response with status code: %d", response.status_code
                )

                response.raise_for_status()
                data = response.json()

                # Check different possible response structures
                if data.get("success") and "ok" in data and "entries" in data["ok"]:
                    tweets = data["ok"]["entries"]
                    logger.info(
                        "Successfully retrieved %d tweets from entries field",
                        len(tweets),
                    )
                    return tweets
                elif data.get("success") and "ok" in data and "tweets" in data["ok"]:
                    tweets = data["ok"]["tweets"]
                    logger.info("Successfully retrieved %d tweets", len(tweets))
                    return tweets
                elif data.get("success") and "ok" in data and "posts" in data["ok"]:
                    tweets = data["ok"]["posts"]
                    logger.info(
                        "Successfully retrieved %d tweets from posts field", len(tweets)
                    )
                    return tweets
                elif data.get("success") and "ok" in data and "feed" in data["ok"]:
                    tweets = data["ok"]["feed"]
                    logger.info(
                        "Successfully retrieved %d tweets from feed field", len(tweets)
                    )
                    return tweets
                elif (
                    data.get("success")
                    and "ok" in data
                    and isinstance(data["ok"], list)
                ):
                    tweets = data["ok"]
                    logger.info(
                        "Successfully retrieved %d tweets from ok list", len(tweets)
                    )
                    return tweets
                elif data.get("success") and isinstance(data.get("tweets"), list):
                    tweets = data["tweets"]
                    logger.info(
                        "Successfully retrieved %d tweets from top level tweets",
                        len(tweets),
                    )
                    return tweets
                elif data.get("success") and isinstance(data.get("posts"), list):
                    tweets = data["posts"]
                    logger.info(
                        "Successfully retrieved %d tweets from top level posts",
                        len(tweets),
                    )
                    return tweets
                elif data.get("success") and isinstance(data.get("feed"), list):
                    tweets = data["feed"]
                    logger.info(
                        "Successfully retrieved %d tweets from top level feed",
                        len(tweets),
                    )
                    return tweets
                elif data.get("success") and isinstance(data.get("entries"), list):
                    tweets = data["entries"]
                    logger.info(
                        "Successfully retrieved %d tweets from top level entries",
                        len(tweets),
                    )
                    return tweets
                elif "tweets" in data and isinstance(data["tweets"], list):
                    tweets = data["tweets"]
                    logger.info(
                        "Successfully retrieved %d tweets from direct tweets field",
                        len(tweets),
                    )
                    return tweets
                elif "posts" in data and isinstance(data["posts"], list):
                    tweets = data["posts"]
                    logger.info(
                        "Successfully retrieved %d tweets from direct posts field",
                        len(tweets),
                    )
                    return tweets
                elif "feed" in data and isinstance(data["feed"], list):
                    tweets = data["feed"]
                    logger.info(
                        "Successfully retrieved %d tweets from direct feed field",
                        len(tweets),
                    )
                    return tweets
                elif "entries" in data and isinstance(data["entries"], list):
                    tweets = data["entries"]
                    logger.info(
                        "Successfully retrieved %d tweets from direct entries field",
                        len(tweets),
                    )
                    return tweets
                else:
                    # If we can't find tweets in the expected structure, log the full response
                    logger.error(
                        "Could not find tweets in response structure. Full response: %s",
                        data,
                    )
                    error_msg = data.get(
                        "error", "Unknown error - check API response format"
                    )
                    logger.error("Error in API response: %s", error_msg)
                    return f"Error fetching account feed: {error_msg}"

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %d - %s", e.response.status_code, e.response.text)
            return f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            logger.error("Request error: %s", str(e))
            return f"Request error occurred: {str(e)}"
        except Exception as e:
            logger.exception("Unexpected error occurred")
            return f"An unexpected error occurred: {str(e)}"
