"""Tool for fetching top cryptocurrencies by trading volume via CryptoCompare API."""

import logging
from typing import List, Type

from pydantic import BaseModel, Field

from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool, CryptoCurrency

logger = logging.getLogger(__name__)


class CryptoCompareFetchTopVolumeInput(BaseModel):
    """Input for CryptoCompareFetchTopVolume tool."""

    to_symbol: str = Field(
        "USD", description="Quote currency for volume calculation. Defaults to 'USD'"
    )
    limit: int = Field(
        10,
        description="Number of cryptocurrencies to fetch (max 100)",
        ge=1,
        le=100,
    )


class CryptoCompareFetchTopVolume(CryptoCompareBaseTool):
    """Tool for fetching top cryptocurrencies by trading volume from CryptoCompare.

    This tool uses the CryptoCompare API to retrieve the top cryptocurrencies
    ranked by 24-hour trading volume in a specified quote currency.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "cryptocompare_fetch_top_volume"
    description: str = "Fetch top cryptocurrencies ranked by 24-hour trading volume"
    args_schema: Type[BaseModel] = CryptoCompareFetchTopVolumeInput

    async def _arun(
        self,
        to_symbol: str = "USD",
        limit: int = 10,
        **kwargs,
    ) -> List[CryptoCurrency]:
        """Async implementation of the tool to fetch top cryptocurrencies by trading volume.

        Args:
            to_symbol: Quote currency for volume calculation. Defaults to 'USD'
            limit: Number of cryptocurrencies to fetch (max 100)
            config: The configuration for the runnable, containing agent context.

        Returns:
            List[CryptoCurrency]: A list of top cryptocurrencies by trading volume.

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

            # Fetch top volume data directly
            volume_data = await self.fetch_top_volume(api_key, limit, to_symbol)

            # Check for errors
            if "error" in volume_data:
                raise ValueError(volume_data["error"])

            # Convert to list of CryptoCurrency objects
            result = []
            if "Data" in volume_data and volume_data["Data"]:
                for item in volume_data["Data"]:
                    coin_info = item.get("CoinInfo", {})
                    raw_data = item.get("RAW", {}).get(to_symbol, {})

                    result.append(
                        CryptoCurrency(
                            id=str(coin_info.get("Id", "")),
                            name=coin_info.get("Name", ""),
                            symbol=coin_info.get(
                                "Name", ""
                            ),  # API uses same field for symbol
                            full_name=coin_info.get("FullName", ""),
                            market_cap=raw_data.get("MKTCAP", 0),
                            volume24h=raw_data.get("VOLUME24HOUR", 0),
                            price=raw_data.get("PRICE", 0),
                            change24h=raw_data.get("CHANGEPCT24HOUR", 0),
                        )
                    )

            return result

        except Exception as e:
            logger.error("Error fetching top volume: %s", str(e))
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
