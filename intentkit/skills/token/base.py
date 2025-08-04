"""Base class for token-related skills."""

import logging
from typing import Any, Dict

import aiohttp

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill
from intentkit.skills.token.constants import MORALIS_API_BASE_URL

logger = logging.getLogger(__name__)


class TokenBaseTool(IntentKitSkill):
    """Base class for all token-related skills.

    This base class provides common functionality for token API interactions,
    including making HTTP requests to the Moralis API.
    """

    def __init__(self, skill_store: SkillStoreABC = None):
        """Initialize the token tool with a skill store."""
        super().__init__(skill_store=skill_store)

    @property
    def category(self) -> str:
        return "token"

    def get_api_key(self) -> str:
        """Get API key from agent config or system config.

        Returns:
            The API key to use for API requests
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        if skill_config.get("api_key_provider") == "agent_owner":
            return skill_config.get("api_key")
        return self.skill_store.get_system_config("moralis_api_key")

    def _prepare_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
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
        params: Dict[str, Any] = None,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
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
                        logger.error(f"API error {response.status}: {error_text}")
                        return {
                            "error": f"API error: {response.status}",
                            "details": error_text,
                        }

                    return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error making request: {str(e)}")
            return {"error": f"HTTP error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error making request: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}
