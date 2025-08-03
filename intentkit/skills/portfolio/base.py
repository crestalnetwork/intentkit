"""Base classes for portfolio skills."""

import asyncio
import logging
from abc import ABC
from typing import Any, Dict, Type

import aiohttp
from pydantic import BaseModel, Field

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import IntentKitSkill
from intentkit.skills.portfolio.constants import MORALIS_API_BASE_URL

logger = logging.getLogger(__name__)


class PortfolioBaseTool(IntentKitSkill, ABC):
    """Base class for portfolio analysis skills."""

    name: str = Field(description="The name of the tool")
    description: str = Field(description="A description of what the tool does")
    args_schema: Type[BaseModel]
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    def get_api_key(self) -> str:
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        if skill_config.get("api_key_provider") == "agent_owner":
            return skill_config.get("api_key")
        return self.skill_store.get_system_config("moralis_api_key")

    @property
    def category(self) -> str:
        return "portfolio"

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
                    logger.error(f"portfolio/base.py: API error: {error_text}")
                    return {
                        "error": f"API error: {response.status}",
                        "details": error_text,
                    }

                return await response.json()

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool synchronously by running the async version in a loop."""
        return asyncio.run(self._arun(*args, **kwargs))
