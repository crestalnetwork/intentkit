import json
import logging
from typing import Any, Dict, Optional, Tuple

import httpx
from pydantic import Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)

DEXSCREENER_BASE_URL = "https://api.dexscreener.com"

# Removed DexScreenerApiError as it won't be raised by _get anymore

# ApiResult still represents (success_data, error_data)
ApiResult = Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]


class DexScreenerBaseTool(IntentKitSkill):
    """
    Generic base class for tools interacting with the Dex Screener API.
    Handles shared logic like API calls and error reporting via return values.
    """

    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data and configs."
    )
    base_url: str = DEXSCREENER_BASE_URL

    @property
    def category(self) -> str:
        return "dexscreener"

    async def _get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> ApiResult:
        """
        Makes an asynchronous GET request to the DexScreener API.

        Args:
            path: The API endpoint path (e.g., "/dex/search").
            params: Optional dictionary of query parameters.

        Returns:
            A tuple (data, error_details):
            - (dict, None): On HTTP 2xx success with valid JSON response.
            - (None, dict): On any error (API error, connection error,
                            JSON parsing error, unexpected error). The dict
                            contains details including an 'error_type'.
        """
        if not path.startswith("/"):
            path = "/" + path

        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        method = "GET"

        logger.debug(f"Calling DexScreener API: {method} {url} with params: {params}")
        response = None  # Define response outside try block for access in except

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method, url, params=params, headers=headers
                )

                # Attempt to parse JSON response text
                try:
                    response_data = response.json()
                except json.JSONDecodeError as json_err:
                    logger.error(
                        f"Failed to parse JSON response from {url}. Status: {response.status_code}. Response text: {response.text}",
                        exc_info=True,
                    )
                    error_details = {
                        "error": "Failed to parse DexScreener API response",
                        "error_type": "parsing_error",
                        "status_code": response.status_code,
                        "details": response.text,  # Raw text causing the error
                        "original_exception": str(json_err),
                        "url": url,
                    }
                    return None, error_details  # Return parsing error

                # Check HTTP status *after* attempting JSON parse
                if response.is_success:  # 2xx
                    logger.debug(
                        f"DexScreener API success response status: {response.status_code}"
                    )
                    return response_data, None  # Success
                else:  # 4xx/5xx
                    logger.warning(
                        f"DexScreener API returned error status: {response.status_code} - {response.text}"
                    )
                    error_details = {
                        "error": "DexScreener API request failed",
                        "error_type": "api_error",
                        "status_code": response.status_code,
                        "response_body": response_data,  # Parsed error body if available
                        "url": url,
                    }
                    return None, error_details  # Return API error

        except httpx.RequestError as req_err:
            logger.error(
                f"Request error connecting to DexScreener API: {req_err}", exc_info=True
            )
            error_details = {
                "error": "Failed to connect to DexScreener API",
                "error_type": "connection_error",
                "details": str(req_err),
                "url": url,
            }
            return None, error_details  # Return connection error

        except Exception as e:
            # Catch any other unexpected errors during the process
            logger.exception(
                f"An unexpected error occurred during DexScreener API GET call: {e}"
            )
            status_code = response.status_code if response else None
            error_details = {
                "error": "An unexpected error occurred during API call",
                "error_type": "unexpected_error",
                "status_code": status_code,  # Include if available
                "details": str(e),
                "url": url,
            }
            return None, error_details  # Return unexpected error
