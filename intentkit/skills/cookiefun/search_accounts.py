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
    """Sort options for account search results."""

    SmartEngagementPoints = 0
    Impressions = 1
    MatchingTweetsCount = 2


class SortOrder(IntEnum):
    """Sort order options."""

    Ascending = 0
    Descending = 1


class SearchAccountsInput(BaseModel):
    """Input for SearchAccounts tool."""

    searchQuery: str = Field(
        description="Search query to find Twitter accounts that authored tweets matching the criteria"
    )

    type: Optional[int] = Field(
        default=None,
        description="Type of tweets to search for: 0 for Original, 1 for Reply, 2 for Quote (leave empty for all types)",
    )

    sortBy: Optional[int] = Field(
        default=None,
        description="Sort by: 0 for SmartEngagementPoints, 1 for Impressions, 2 for MatchingTweetsCount",
    )

    sortOrder: Optional[int] = Field(
        default=None,
        description="Sort order: 0 for Ascending, 1 for Descending",
    )


class SearchAccounts(CookieFunBaseTool):
    """Tool to search for Twitter accounts based on tweet content."""

    name: str = "cookiefun_search_accounts"
    description: str = "Searches for Twitter accounts that authored tweets matching specified search criteria."
    args_schema: Type[BaseModel] = SearchAccountsInput

    async def _arun(
        self,
        searchQuery: str,
        type: Optional[int] = None,
        sortBy: Optional[int] = None,
        sortOrder: Optional[int] = None,
        **kwargs,
    ) -> Union[List[Dict[str, Any]], str]:
        """
        Search for Twitter accounts based on tweet content.

        Args:
            searchQuery: Search query to match tweet content
            type: Type of tweets to search for (0=Original, 1=Reply, 2=Quote)
            sortBy: Sort by field (0=SmartEngagementPoints, 1=Impressions, 2=MatchingTweetsCount)
            sortOrder: Sort order (0=Ascending, 1=Descending)

        Returns:
            List of Twitter accounts matching the search criteria with metrics.
        """
        logger.info(
            "Searching accounts with query=%s, type=%s, sortBy=%s, sortOrder=%s",
            searchQuery,
            type,
            sortBy,
            sortOrder,
        )

        if not searchQuery:
            logger.error("No search query provided")
            return "Error: searchQuery is required."

        try:
            # Get context to retrieve API key
            api_key = self.get_api_key()

            if not api_key:
                logger.error("No API key provided for CookieFun API")
                return "Error: No API key provided for CookieFun API. Please configure the API key in the agent settings."

            # Prepare request payload
            payload = {"searchQuery": searchQuery}

            # Add optional parameters if provided
            if type is not None:
                payload["type"] = type
            if sortBy is not None:
                payload["sortBy"] = sortBy
            if sortOrder is not None:
                payload["sortOrder"] = sortOrder

            # Make API request
            headers = {**DEFAULT_HEADERS, "x-api-key": api_key}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ENDPOINTS["search_accounts"], headers=headers, json=payload
                )
                logger.debug(
                    "Received response with status code: %d", response.status_code
                )

                response.raise_for_status()
                data = response.json()

                # Check different possible response structures
                if data.get("success") and "ok" in data and "entries" in data["ok"]:
                    accounts = data["ok"]["entries"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from entries field",
                        len(accounts),
                    )
                    return accounts
                elif data.get("success") and "ok" in data and "accounts" in data["ok"]:
                    accounts = data["ok"]["accounts"]
                    logger.info(
                        "Successfully retrieved %d matching accounts", len(accounts)
                    )
                    return accounts
                elif data.get("success") and "ok" in data and "results" in data["ok"]:
                    accounts = data["ok"]["results"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from results field",
                        len(accounts),
                    )
                    return accounts
                elif (
                    data.get("success")
                    and "ok" in data
                    and isinstance(data["ok"], list)
                ):
                    accounts = data["ok"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from ok list",
                        len(accounts),
                    )
                    return accounts
                elif data.get("success") and isinstance(data.get("accounts"), list):
                    accounts = data["accounts"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from top level accounts",
                        len(accounts),
                    )
                    return accounts
                elif data.get("success") and isinstance(data.get("results"), list):
                    accounts = data["results"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from top level results",
                        len(accounts),
                    )
                    return accounts
                elif data.get("success") and isinstance(data.get("entries"), list):
                    accounts = data["entries"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from top level entries",
                        len(accounts),
                    )
                    return accounts
                elif "accounts" in data and isinstance(data["accounts"], list):
                    accounts = data["accounts"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from direct accounts field",
                        len(accounts),
                    )
                    return accounts
                elif "results" in data and isinstance(data["results"], list):
                    accounts = data["results"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from direct results field",
                        len(accounts),
                    )
                    return accounts
                elif "entries" in data and isinstance(data["entries"], list):
                    accounts = data["entries"]
                    logger.info(
                        "Successfully retrieved %d matching accounts from direct entries field",
                        len(accounts),
                    )
                    return accounts
                else:
                    # If we can't find accounts in the expected structure, log the full response
                    logger.error(
                        "Could not find matching accounts in response structure. Full response: %s",
                        data,
                    )
                    error_msg = data.get(
                        "error", "Unknown error - check API response format"
                    )
                    logger.error("Error in API response: %s", error_msg)
                    return f"Error searching accounts: {error_msg}"

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %d - %s", e.response.status_code, e.response.text)
            return f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            logger.error("Request error: %s", str(e))
            return f"Request error occurred: {str(e)}"
        except Exception as e:
            logger.exception("Unexpected error occurred")
            return f"An unexpected error occurred: {str(e)}"
