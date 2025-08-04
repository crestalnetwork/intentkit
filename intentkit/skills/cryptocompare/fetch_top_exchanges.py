"""Tool for fetching top exchanges for a cryptocurrency pair via CryptoCompare API."""

import logging
from typing import List, Type

from pydantic import BaseModel, Field

from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool, CryptoExchange

logger = logging.getLogger(__name__)


class CryptoCompareFetchTopExchangesInput(BaseModel):
    """Input for CryptoCompareFetchTopExchanges tool."""

    from_symbol: str = Field(
        ..., description="Base cryptocurrency symbol for the trading pair (e.g., 'BTC')"
    )
    to_symbol: str = Field(
        "USD",
        description="Quote currency symbol for the trading pair. Defaults to 'USD'",
    )
    limit: int = Field(
        10,
        description="Number of exchanges to fetch (max 100)",
        ge=1,
        le=100,
    )


class CryptoCompareFetchTopExchanges(CryptoCompareBaseTool):
    """Tool for fetching top exchanges for a cryptocurrency pair from CryptoCompare.

    This tool uses the CryptoCompare API to retrieve the top exchanges
    for a specific cryptocurrency trading pair, ranked by volume.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "cryptocompare_fetch_top_exchanges"
    description: str = (
        "Fetch top exchanges for a cryptocurrency trading pair, ranked by volume"
    )
    args_schema: Type[BaseModel] = CryptoCompareFetchTopExchangesInput

    async def _arun(
        self,
        from_symbol: str,
        to_symbol: str = "USD",
        limit: int = 10,
        **kwargs,
    ) -> List[CryptoExchange]:
        """Async implementation of the tool to fetch top exchanges for a cryptocurrency pair.

        Args:
            from_symbol: Base cryptocurrency symbol for the trading pair (e.g., 'BTC')
            to_symbol: Quote currency symbol for the trading pair. Defaults to 'USD'
            limit: Number of exchanges to fetch (max 100)
            config: The configuration for the runnable, containing agent context.

        Returns:
            List[CryptoExchange]: A list of top exchanges for the specified trading pair.

        Raises:
            Exception: If there's an error accessing the CryptoCompare API.
        """
        try:
            context = self.get_context()
            skill_config = context.agent.skill_config(self.category)

            # Check rate limit
            await self.check_rate_limit(context.agent_id, max_requests=5, interval=60)

            # Get API key from context
            api_key = skill_config.get("api_key")
            if not api_key:
                raise ValueError("CryptoCompare API key not found in configuration")

            # Fetch top exchanges data directly
            exchanges_data = await self.fetch_top_exchanges(
                api_key, from_symbol, to_symbol
            )

            # Check for errors
            if "error" in exchanges_data:
                raise ValueError(exchanges_data["error"])

            # Convert to list of CryptoExchange objects
            result = []
            if "Data" in exchanges_data and exchanges_data["Data"]:
                for item in exchanges_data["Data"]:
                    if len(result) >= limit:
                        break

                    result.append(
                        CryptoExchange(
                            exchange=item.get("exchange", ""),
                            from_symbol=from_symbol,
                            to_symbol=to_symbol,
                            volume24h=item.get("volume24h", 0),
                            volume24h_to=item.get("volume24hTo", 0),
                        )
                    )

            return result

        except Exception as e:
            logger.error("Error fetching top exchanges: %s", str(e))
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
