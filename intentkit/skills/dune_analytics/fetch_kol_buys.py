"""Skill to fetch KOL memecoin buys on Solana from Dune Analytics API.

Uses query ID 4832844 to retrieve a list of KOL buy transactions.
"""

from typing import Any, Dict, Type

import httpx
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.dune_analytics.base import DuneBaseTool

BASE_URL = "https://api.dune.com/api/v1/query"
KOL_BUYS_QUERY_ID = 4832844


class KOLBuysInput(BaseModel):
    """Input schema for fetching KOL memecoin buys."""

    limit: int = Field(
        default=10,
        description="Maximum number of buy transactions to fetch (default 10).",
        ge=1,
    )


class KOLBuyData(BaseModel):
    """Data model for KOL buy results."""

    data: Dict[str, Any] = Field(description="KOL buy data from Dune API")
    error: str = Field(default="", description="Error message if fetch failed")


class KOLBuysOutput(BaseModel):
    """Output schema for KOL memecoin buys."""

    buys: KOLBuyData = Field(description="KOL buy transaction data")
    summary: str = Field(description="Summary of fetched data")


class FetchKOLBuys(DuneBaseTool):
    """Skill to fetch KOL memecoin buys on Solana from Dune Analytics API."""

    name: str = "dune_fetch_kol_buys"
    description: str = (
        "Fetches a list of KOL memecoin buy transactions on Solana from Dune Analytics API using query ID 4832844. "
        "Supports a configurable limit for the number of results. Handles rate limits with retries."
    )
    args_schema: Type[BaseModel] = KOLBuysInput
    skill_store: SkillStoreABC = Field(description="Skill store for data persistence")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=5, min=5, max=60)
    )
    async def fetch_data(
        self, query_id: int, api_key: str, limit: int = 10
    ) -> Dict[str, Any]:
        """Fetch data for a specific Dune query.

        Args:
            query_id: Dune query ID.
            api_key: Dune API key.
            limit: Maximum number of results (default 10).

        Returns:
            Dictionary of query results.

        Raises:
            ToolException: If the API request fails.
        """
        from langchain.tools.base import ToolException

        url = f"{BASE_URL}/{query_id}/results?limit={limit}"
        headers = {"X-Dune-API-Key": api_key}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                return response.json().get("result", {})
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                raise ToolException(f"Error fetching data from Dune API: {e}")

    async def _arun(
        self,
        limit: int = 10,
        **kwargs,
    ) -> str:
        """Fetch KOL memecoin buys asynchronously and return formatted output.

        Args:
            limit: Maximum number of buy transactions to fetch (default 10).
            config: Runnable configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            Formatted string with KOL buy transactions or error message.
        """
        import logging

        logger = logging.getLogger(__name__)
        api_key = self.get_api_key()

        try:
            data = await self.fetch_data(KOL_BUYS_QUERY_ID, api_key, limit)
            rows = data.get("rows", [])
            if not rows:
                return "No KOL buy transactions found."

            output = f"Fetched {len(rows)} KOL memecoin buy transactions:\n"
            for row in rows:
                output += (
                    f"- {row['kol_with_link']} bought {row['token_with_chart']} "
                    f"(${row['amount_usd']:.2f}) at {row['buy_time']}\n"
                )
            return output.strip()
        except Exception as e:
            error_msg = f"Error fetching KOL memecoin buys: {str(e)}"
            logger.warning(error_msg)
            return error_msg

    def _run(self, question: str):
        raise NotImplementedError("Use _arun for async execution")
