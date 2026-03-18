"""Tool for fetching top exchanges for a cryptocurrency pair via CryptoCompare API."""

import logging

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool, CryptoExchange

logger = logging.getLogger(__name__)


class CryptoCompareFetchTopExchangesInput(BaseModel):
    """Input for CryptoCompareFetchTopExchanges tool."""

    from_symbol: str = Field(..., description="Base crypto symbol (e.g., BTC)")
    to_symbol: str = Field("USD", description="Quote currency symbol")
    limit: int = Field(
        10,
        description="Number of results (max 100)",
        ge=1,
        le=100,
    )


class CryptoCompareFetchTopExchanges(CryptoCompareBaseTool):
    """Tool for fetching top exchanges from CryptoCompare."""

    name: str = "cryptocompare_fetch_top_exchanges"
    description: str = "Fetch top exchanges for a crypto pair, ranked by volume."
    args_schema: ArgsSchema | None = CryptoCompareFetchTopExchangesInput

    async def _arun(
        self,
        from_symbol: str,
        to_symbol: str = "USD",
        limit: int = 10,
        **kwargs,
    ) -> list[CryptoExchange]:
        """Async implementation of the tool to fetch top exchanges for a cryptocurrency pair.

        Args:
            from_symbol: Base cryptocurrency symbol for the trading pair (e.g., 'BTC')
            to_symbol: Quote currency symbol for the trading pair. Defaults to 'USD'
            limit: Number of exchanges to fetch (max 100)
            config: The configuration for the runnable, containing agent context.

        Returns:
            list[CryptoExchange]: A list of top exchanges for the specified trading pair.

        Raises:
            Exception: If there's an error accessing the CryptoCompare API.
        """
        try:
            context = self.get_context()

            # Check rate limit
            await self.check_rate_limit(max_requests=5, interval=60)

            # Get API key from platform config
            api_key = self.get_api_key()

            # Fetch top exchanges data directly
            exchanges_data = await self.fetch_top_exchanges(
                api_key, from_symbol, to_symbol
            )

            # Check for errors
            if "error" in exchanges_data:
                raise ToolException(exchanges_data["error"])

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
