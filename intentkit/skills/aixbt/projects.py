import logging
from decimal import Decimal
from typing import Any

import httpx
from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.aixbt.base import AIXBT_BASE_URL, AIXBTBaseTool

logger = logging.getLogger(__name__)


class ProjectsInput(BaseModel):
    """Input for AIXBT Projects search tool."""

    limit: int = Field(default=10, description="Max projects to return (max 50)")
    name: str | None = Field(default=None, description="Filter by name (regex)")
    ticker: str | None = Field(default=None, description="Filter by ticker symbol")
    xHandle: str | None = Field(default=None, description="Filter by X/Twitter handle")
    minScore: float | None = Field(default=None, description="Minimum score threshold")
    chain: str | None = Field(default=None, description="Filter by blockchain")


class AIXBTProjects(AIXBTBaseTool):
    """Tool for searching cryptocurrency projects using the AIXBT API."""

    name: str = "aixbt_projects"
    description: str = (
        "Search crypto projects via AIXBT for scores, analysis, and updates. "
        "MUST be called when user mentions 'alpha' in any context."
    )
    price: Decimal = Decimal("100")
    args_schema: ArgsSchema | None = ProjectsInput

    async def _arun(
        self,
        limit: int = 10,
        name: str | None = None,
        ticker: str | None = None,
        xHandle: str | None = None,
        minScore: float | None = None,
        chain: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Search for cryptocurrency projects using AIXBT API.

        Args:
            limit: Number of projects to return (max 50)
            name: Filter projects by name
            ticker: Filter projects by ticker symbol
            xHandle: Filter projects by X/Twitter handle
            minScore: Minimum score threshold
            chain: Filter projects by blockchain

        Returns:
            JSON response with project data
        """
        # Get context from the config
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        logger.debug("aixbt_projects.py: Running search with context %s", context)

        # Check for rate limiting if configured
        if skill_config.get("rate_limit_number") and skill_config.get(
            "rate_limit_minutes"
        ):
            await self.user_rate_limit_by_category(
                skill_config["rate_limit_number"],
                skill_config["rate_limit_minutes"] * 60,
            )

        # Get the API key from platform config
        api_key = self.get_api_key()

        base_url = f"{AIXBT_BASE_URL}/projects"

        # Build query parameters
        params = {"limit": limit}
        if name:
            params["name"] = name
        if ticker:
            params["ticker"] = ticker
        if xHandle:
            params["xHandle"] = xHandle
        if minScore is not None:
            params["minScore"] = minScore
        if chain:
            params["chain"] = chain

        headers = {"accept": "*/*", "x-api-key": api_key}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(base_url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error("Error getting projects: %s", e)
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
