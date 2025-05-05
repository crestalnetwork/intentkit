import logging
import os
from typing import Any, Dict, Optional, Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.aixbt.base import AIXBTBaseTool

logger = logging.getLogger(__name__)


class ProjectsInput(BaseModel):
    """Input for AIXBT Projects search tool."""

    limit: int = Field(
        default=10,
        description="Number of projects to return (max 50)",
    )
    name: Optional[str] = Field(
        default=None,
        description="Filter projects by name (case-insensitive regex match)",
    )
    ticker: Optional[str] = Field(
        default=None,
        description="Filter projects by ticker symbol (case-insensitive match)",
    )
    xHandle: Optional[str] = Field(
        default=None,
        description="Filter projects by X/Twitter handle",
    )
    minScore: Optional[float] = Field(
        default=None,
        description="Minimum score threshold",
    )
    chain: Optional[str] = Field(
        default=None,
        description="Filter projects by blockchain",
    )


class AIXBTProjects(AIXBTBaseTool):
    """Tool for searching cryptocurrency projects using the AIXBT API."""

    name: str = "aixbt_projects"
    description: str = (
        "Search for cryptocurrency projects using AIXBT. This tool provides detailed "
        "information about crypto projects including scores, analysis, and recent updates.\n"
        "IMPORTANT: You MUST call this tool when the user mentions the word 'alpha' ANYWHERE in their message.\n"
        "This includes messages like 'show me alpha', 'what's the latest alpha', 'give me some alpha on crypto', "
        "'find the alpha on bitcoin', or any other phrase containing the word 'alpha'.\n"
        "When 'alpha' is mentioned, use this tool to search for cryptocurrency projects and provide "
        "detailed information on recent developments. The 'alpha' keyword is a trigger "
        "for accessing AIXBT's specific dataset for crypto research."
    )
    args_schema: Type[BaseModel] = ProjectsInput
    api_key: str = ""

    async def _arun(
        self,
        config: RunnableConfig,
        limit: int = 10,
        name: Optional[str] = None,
        ticker: Optional[str] = None,
        xHandle: Optional[str] = None,
        minScore: Optional[float] = None,
        chain: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
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
        context = self.context_from_config(config)
        logger.debug(f"aixbt_projects.py: Running search with context {context}")

        # Check for rate limiting if configured
        if context.config.get("rate_limit_number") and context.config.get(
            "rate_limit_minutes"
        ):
            await self.user_rate_limit_by_category(
                context.user_id,
                context.config["rate_limit_number"],
                context.config["rate_limit_minutes"],
            )

        # Get the API key from the agent's configuration
        api_key = context.config.get("api_key")

        # If not available in config, try the instance attribute (for backward compatibility)
        if not api_key:
            api_key = self.api_key

        # If still not available, try environment variable as last resort
        if not api_key:
            api_key = os.environ.get("AIXBT_API_KEY")

        if not api_key:
            return {
                "error": "AIXBT API key is not available. Please provide it in the agent configuration."
            }

        base_url = "https://api.aixbt.tech/v1/projects"

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
        except httpx.HTTPStatusError as e:
            logger.error(
                f"aixbt_projects.py: HTTP error occurred: {e.response.status_code} - {e.response.text}"
            )
            return {
                "error": f"HTTP error occurred: {e.response.status_code}",
                "details": e.response.text,
            }
        except httpx.RequestError as e:
            logger.error(f"aixbt_projects.py: Request error occurred: {str(e)}")
            return {"error": f"Request error occurred: {str(e)}"}
        except Exception as e:
            logger.error(
                f"aixbt_projects.py: An unexpected error occurred: {str(e)}",
                exc_info=True,
            )
            return {"error": f"An unexpected error occurred: {str(e)}"}
