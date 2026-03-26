"""Tool for fetching top cryptocurrencies by trading volume via CryptoCompare API."""

import logging

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool, CryptoCurrency

logger = logging.getLogger(__name__)


class CryptoCompareFetchTopVolumeInput(BaseModel):
    """Input for CryptoCompareFetchTopVolume tool."""

    to_symbol: str = Field("USD", description="Quote currency symbol")
    limit: int = Field(
        10,
        description="Number of results (max 100)",
        ge=1,
        le=100,
    )


class CryptoCompareFetchTopVolume(CryptoCompareBaseTool):
    """Tool for fetching top cryptocurrencies by trading volume from CryptoCompare."""

    name: str = "cryptocompare_fetch_top_volume"
    description: str = "Fetch top cryptocurrencies ranked by 24h trading volume."
    args_schema: ArgsSchema | None = CryptoCompareFetchTopVolumeInput

    async def _arun(
        self,
        to_symbol: str = "USD",
        limit: int = 10,
        **kwargs,
    ) -> list[CryptoCurrency]:
        """Async implementation of the tool to fetch top cryptocurrencies by trading volume.

        Args:
            to_symbol: Quote currency for volume calculation. Defaults to 'USD'
            limit: Number of cryptocurrencies to fetch (max 100)
            config: The configuration for the runnable, containing agent context.

        Returns:
            list[CryptoCurrency]: A list of top cryptocurrencies by trading volume.

        Raises:
            Exception: If there's an error accessing the CryptoCompare API.
        """
        try:
            self.get_context()

            # Check rate limit
            await self.check_rate_limit(max_requests=5, interval=60)

            # Get API key from platform config
            api_key = self.get_api_key()

            # Fetch top volume data directly
            volume_data = await self.fetch_top_volume(api_key, limit, to_symbol)

            # Check for errors
            if "error" in volume_data:
                raise ToolException(volume_data["error"])

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

        except ToolException:
            raise
        except Exception as e:
            logger.error("Error fetching top volume: %s", e)
            raise ToolException(f"Failed to fetch top volume: {e!s}")
