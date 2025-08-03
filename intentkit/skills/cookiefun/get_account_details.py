from typing import Any, Dict, Optional, Type, Union

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.cookiefun.base import CookieFunBaseTool, logger
from intentkit.skills.cookiefun.constants import DEFAULT_HEADERS, ENDPOINTS


class GetAccountDetailsInput(BaseModel):
    """Input for GetAccountDetails tool."""

    username: Optional[str] = Field(
        default=None,
        description="Twitter username (either username or userId is required)",
    )

    userId: Optional[str] = Field(
        default=None,
        description="Twitter user ID (either username or userId is required)",
    )


class GetAccountDetails(CookieFunBaseTool):
    """Tool to get detailed information about a Twitter account."""

    name: str = "cookiefun_get_account_details"
    description: str = "Retrieves detailed information about a Twitter account including followers, following, posts, metrics, and engagement data."
    args_schema: Type[BaseModel] = GetAccountDetailsInput

    async def _arun(
        self,
        username: Optional[str] = None,
        userId: Optional[str] = None,
        **kwargs,
    ) -> Union[Dict[str, Any], str]:
        """
        Get detailed information about a Twitter account.

        Args:
            username: Twitter username (either username or userId is required)
            userId: Twitter user ID (either username or userId is required)

        Returns:
            Account details including followers, following, posts, metrics, and engagement data.
        """
        logger.info(
            "Getting account details for username=%s, userId=%s", username, userId
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
                    ENDPOINTS["account_details"], headers=headers, json=payload
                )
                logger.debug(
                    "Received response with status code: %d", response.status_code
                )

                response.raise_for_status()
                data = response.json()

                # Check different possible response structures
                if (
                    data.get("success")
                    and "ok" in data
                    and isinstance(data["ok"], dict)
                ):
                    logger.info("Successfully retrieved account details")
                    return data["ok"]
                elif data.get("success") and "ok" in data and "entry" in data["ok"]:
                    logger.info(
                        "Successfully retrieved account details from entry field"
                    )
                    return data["ok"]["entry"]
                elif (
                    data.get("success")
                    and "ok" in data
                    and "entries" in data["ok"]
                    and len(data["ok"]["entries"]) > 0
                ):
                    # If entries is a list but we expect a single account, return the first one
                    logger.info(
                        "Successfully retrieved account details from entries array"
                    )
                    return data["ok"]["entries"][0]
                elif data.get("success") and isinstance(data.get("account"), dict):
                    # If account is at the top level
                    logger.info("Successfully retrieved account details from top level")
                    return data["account"]
                elif data.get("success") and isinstance(data.get("entry"), dict):
                    # If entry is at the top level
                    logger.info(
                        "Successfully retrieved account details from entry field"
                    )
                    return data["entry"]
                elif (
                    data.get("success")
                    and isinstance(data.get("entries"), list)
                    and len(data.get("entries")) > 0
                ):
                    # If entries is at the top level
                    logger.info(
                        "Successfully retrieved account details from entries array at top level"
                    )
                    return data["entries"][0]
                elif "account" in data and isinstance(data["account"], dict):
                    # If only account field exists
                    logger.info("Successfully retrieved account from direct field")
                    return data["account"]
                elif "entry" in data and isinstance(data["entry"], dict):
                    # If only entry field exists
                    logger.info(
                        "Successfully retrieved account from direct entry field"
                    )
                    return data["entry"]
                elif (
                    "entries" in data
                    and isinstance(data["entries"], list)
                    and len(data["entries"]) > 0
                ):
                    # If only entries field exists
                    logger.info(
                        "Successfully retrieved account from direct entries field"
                    )
                    return data["entries"][0]
                else:
                    # If we can't find account details in the expected structure, log the full response
                    logger.error(
                        "Could not find account details in response structure. Full response: %s",
                        data,
                    )
                    error_msg = data.get(
                        "error", "Unknown error - check API response format"
                    )
                    logger.error("Error in API response: %s", error_msg)
                    return f"Error fetching account details: {error_msg}"

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error: %d - %s", e.response.status_code, e.response.text)
            return f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
        except httpx.RequestError as e:
            logger.error("Request error: %s", str(e))
            return f"Request error occurred: {str(e)}"
        except Exception as e:
            logger.exception("Unexpected error occurred")
            return f"An unexpected error occurred: {str(e)}"
