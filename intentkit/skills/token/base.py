"""Base class for token-related skills."""

import logging
from typing import Any

import aiohttp
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill
from intentkit.skills.token.constants import MORALIS_API_BASE_URL

logger = logging.getLogger(__name__)


class TokenBaseTool(IntentKitSkill):
    """Base class for all token-related skills.

    This base class provides common functionality for token API interactions,
    including making HTTP requests to the Moralis API.
    """

    category: str = "token"

    def get_api_key(self) -> str:
        if not config.moralis_api_key:
            raise ToolException("Moralis API key is not configured")
        return config.moralis_api_key

    def _prepare_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Convert boolean values to lowercase strings for API compatibility.

        Args:
            params: Dictionary with query parameters that may contain boolean values

        Returns:
            Dictionary with boolean values converted to lowercase strings
        """
        if not params:
            return params

        result = {}
        for key, value in params.items():
            if isinstance(value, bool):
                result[key] = str(value).lower()
            else:
                result[key] = value
        return result

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        api_key: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a request to the Moralis API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            api_key: Moralis API key
            params: Query parameters
            data: Request body data for POST requests

        Returns:
            Response data as dictionary
        """
        url = f"{MORALIS_API_BASE_URL}{endpoint}"

        if not api_key:
            logger.error("API key is missing")
            return {"error": "API key is missing"}

        headers = {"accept": "application/json", "X-API-Key": api_key}
        processed_params = self._prepare_params(params) if params else None

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=processed_params,
                    json=data,
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.error("API error %s: %s", response.status, error_text)
                        return {
                            "error": f"API error: {response.status}",
                            "details": error_text,
                        }

                    return await response.json()
        except aiohttp.ClientError as e:
            logger.error("HTTP error making request: %s", e)
            return {"error": f"HTTP error: {str(e)}"}
        except Exception as e:
            logger.error("Unexpected error making request: %s", e)
            return {"error": f"Unexpected error: {str(e)}"}
