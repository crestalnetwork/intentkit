from typing import Any, Dict, List, Optional, Type, Union

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.cookiefun.base import CookieFunBaseTool, logger
from intentkit.skills.cookiefun.constants import DEFAULT_HEADERS, ENDPOINTS


class GetAccountSmartFollowersInput(BaseModel):
    """Input for GetAccountSmartFollowers tool."""

    username: Optional[str] = Field(
        default=None,
        description="Twitter username (either username or userId is required)",
    )

    userId: Optional[str] = Field(
        default=None,
        description="Twitter user ID (either username or userId is required)",
    )


class GetAccountSmartFollowers(CookieFunBaseTool):
    """Tool to get smart followers for a Twitter account."""

    name: str = "cookiefun_get_account_smart_followers"
    description: str = "Returns a list of top smart followers for a specific Twitter account, with detailed metrics about these followers."
    args_schema: Type[BaseModel] = GetAccountSmartFollowersInput

    async def _arun(
        self,
        username: Optional[str] = None,
        userId: Optional[str] = None,
        **kwargs,
    ) -> Union[List[Dict[str, Any]], str]:
        """
        Get smart followers for a Twitter account.

        Args:
            username: Twitter username (either username or userId is required)
            userId: Twitter user ID (either username or userId is required)

        Returns:
            List of top smart followers with their metrics.
        """
        logger.info(
            "Getting smart followers for username=%s, userId=%s", username, userId
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

            # Make API request
            headers = {**DEFAULT_HEADERS, "x-api-key": api_key}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    ENDPOINTS["smart_followers"], headers=headers, json=payload
                )
                logger.debug(
                    "Received response with status code: %d", response.status_code
                )

                response.raise_for_status()
                data = response.json()

                # Check different possible response structures
                if data.get("success") and "ok" in data and "entries" in data["ok"]:
                    followers = data["ok"]["entries"]
                    logger.info(
                        "Successfully retrieved %d smart followers from entries field",
                        len(followers),
                    )
                    return followers
                elif data.get("success") and "ok" in data and "accounts" in data["ok"]:
                    followers = data["ok"]["accounts"]
                    logger.info(
                        "Successfully retrieved %d smart followers", len(followers)
                    )
                    return followers
                elif data.get("success") and "ok" in data and "followers" in data["ok"]:
                    followers = data["ok"]["followers"]
                    logger.info(
                        "Successfully retrieved %d smart followers from followers field",
                        len(followers),
                    )
                    return followers
                elif (
                    data.get("success")
                    and "ok" in data
                    and isinstance(data["ok"], list)
                ):
                    followers = data["ok"]
                    logger.info(
                        "Successfully retrieved %d smart followers from ok list",
                        len(followers),
                    )
                    return followers
                elif data.get("success") and isinstance(data.get("accounts"), list):
                    followers = data["accounts"]
                    logger.info(
                        "Successfully retrieved %d smart followers from top level accounts",
                        len(followers),
                    )
                    return followers
                elif data.get("success") and isinstance(data.get("followers"), list):
                    followers = data["followers"]
                    logger.info(
                        "Successfully retrieved %d smart followers from top level followers",
                        len(followers),
                    )
                    return followers
                elif data.get("success") and isinstance(data.get("entries"), list):
                    followers = data["entries"]
                    logger.info(
                        "Successfully retrieved %d smart followers from top level entries",
                        len(followers),
                    )
                    return followers
                elif "followers" in data and isinstance(data["followers"], list):
                    followers = data["followers"]
                    logger.info(
                        "Successfully retrieved %d smart followers from direct followers field",
                        len(followers),
                    )
                    return followers
                elif "accounts" in data and isinstance(data["accounts"], list):
                    followers = data["accounts"]
                    logger.info(
                        "Successfully retrieved %d smart followers from direct accounts field",
                        len(followers),
                    )
                    return followers
                elif "entries" in data and isinstance(data["entries"], list):
                    followers = data["entries"]
                    logger.info(
                        "Successfully retrieved %d smart followers from direct entries field",
                        len(followers),
                    )
                    return followers
                else:
                    # If we can't find followers in the expected structure, log the full response
                    logger.error(
                        "Could not find smart followers in response structure. Full response: %s",
                        data,
                    )
                    error_msg = data.get(
                        "error", "Unknown error - check API response format"
                    )
                    logger.error("Error in API response: %s", error_msg)
                    return f"Error fetching smart followers: {error_msg}"

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %d - %s", e.response.status_code, e.response.text)
            return f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            logger.error("Request error: %s", str(e))
            return f"Request error occurred: {str(e)}"
        except Exception as e:
            logger.exception("Unexpected error occurred")
            return f"An unexpected error occurred: {str(e)}"
