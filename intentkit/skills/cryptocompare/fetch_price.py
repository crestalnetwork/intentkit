"""Tool for fetching cryptocurrency prices via CryptoCompare API."""

import logging
from typing import List, Type

from pydantic import BaseModel, Field

from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool, CryptoPrice

logger = logging.getLogger(__name__)


class CryptoCompareFetchPriceInput(BaseModel):
    """Input for CryptoCompareFetchPrice tool."""

    from_symbol: str = Field(
        ...,
        description="Base cryptocurrency symbol to get prices for (e.g., 'BTC', 'ETH')",
    )
    to_symbols: List[str] = Field(
        ...,
        description="List of target currencies (fiat or crypto) (e.g., ['USD', 'EUR', 'JPY'])",
    )


class CryptoCompareFetchPrice(CryptoCompareBaseTool):
    """Tool for fetching cryptocurrency prices from CryptoCompare.

    This tool uses the CryptoCompare API to retrieve real-time cryptocurrency price data
    with multi-currency support. Provide a base currency (e.g., 'BTC', 'ETH') and a list
    of target currencies (e.g., ['USD', 'EUR', 'JPY']) to get current exchange rates.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "cryptocompare_fetch_price"
    description: str = (
        "Fetch real-time cryptocurrency price data with multi-currency support"
    )
    args_schema: Type[BaseModel] = CryptoCompareFetchPriceInput

    async def _arun(
        self,
        from_symbol: str,
        to_symbols: List[str],
        **kwargs,
    ) -> List[CryptoPrice]:
        """Async implementation of the tool to fetch cryptocurrency prices.

        Args:
            from_symbol: Base cryptocurrency symbol to get prices for (e.g., 'BTC', 'ETH')
            to_symbols: List of target currencies (fiat or crypto) (e.g., ['USD', 'EUR', 'JPY'])
            config: The configuration for the runnable, containing agent context.

        Returns:
            List[CryptoPrice]: A list of cryptocurrency prices for each target currency.

        Raises:
            Exception: If there's an error accessing the CryptoCompare API.
        """
        try:
            context = self.get_context()
            skill_config = context.agent.skill_config(self.category)

            # Check rate limit
            await self.check_rate_limit(context.agent_id, max_requests=10, interval=60)

            # Get API key from context
            api_key = skill_config.get("api_key")
            if not api_key:
                raise ValueError("CryptoCompare API key not found in configuration")

            # Fetch price data directly
            price_data = await self.fetch_price(api_key, from_symbol, to_symbols)

            # Check for errors
            if "error" in price_data:
                raise ValueError(price_data["error"])

            # Convert to list of CryptoPrice objects
            result = []
            for to_symbol, price in price_data.items():
                result.append(
                    CryptoPrice(
                        from_symbol=from_symbol,
                        to_symbol=to_symbol,
                        price=price,
                    )
                )

            return result

        except Exception as e:
            logger.error("Error fetching price: %s", str(e))
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
