"""Base classes for portfolio skills."""

import asyncio
import logging
from abc import ABC
from typing import Any

import aiohttp
from langchain_core.tools import ToolException
from pydantic import BaseModel, Field

from intentkit.config.config import config
from intentkit.skills.base import IntentKitSkill
from intentkit.skills.portfolio.constants import MORALIS_API_BASE_URL

logger = logging.getLogger(__name__)


class PortfolioBaseTool(IntentKitSkill, ABC):
    """Base class for portfolio analysis skills."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: type[BaseModel]

    def get_api_key(self) -> str:
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        if skill_config.get("api_key_provider") == "agent_owner":
            api_key = skill_config.get("api_key")
        else:
            api_key = config.moralis_api_key

        if not api_key:
            raise ToolException("Moralis API key is not configured.")

        return api_key

    @property
    def category(self) -> str:
        return "portfolio"

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
        params: dict[str, Any] = None,
        data: dict[str, Any] = None,
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

        headers = {"accept": "application/json", "X-API-Key": api_key}

        # Convert boolean params to strings
        processed_params = self._prepare_params(params) if params else None

        logger.debug(f"portfolio/base.py: Making request to {url}")

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
                    logger.error(
                        "portfolio/base.py: API error %s for %s", response.status, url
                    )
                    raise ToolException(
                        f"Moralis API error: {response.status} - {error_text}"
                    )

                try:
                    return await response.json()
                except aiohttp.ContentTypeError as exc:
                    await response.text()
                    logger.error(
                        "portfolio/base.py: Failed to decode JSON response from %s", url
                    )
                    raise ToolException(
                        "Moralis API returned invalid JSON payload."
                    ) from exc

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool synchronously by running the async version in a loop."""
        return asyncio.run(self._arun(*args, **kwargs))
