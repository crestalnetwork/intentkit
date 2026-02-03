"""Pyth fetch_price_feed skill."""

import json

import httpx
from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.pyth.base import PythBaseTool


class FetchPriceFeedInput(BaseModel):
    """Input schema for fetching Pyth price feed ID."""

    token_symbol: str = Field(
        ..., description="The asset ticker/symbol to fetch the price feed ID for"
    )
    quote_currency: str = Field(
        default="USD", description="The quote currency to filter by (defaults to USD)"
    )
    asset_type: str = Field(
        default="crypto",
        description="The asset type to search for (crypto, equity, fx, metal)",
    )


class PythFetchPriceFeed(PythBaseTool):
    """Fetch the price feed ID for a given token symbol from Pyth.

    This tool queries the Pyth Hermes API to find the price feed ID
    for a given asset symbol.
    """

    name: str = "pyth_fetch_price_feed"
    description: str = """Fetch the price feed ID for a given token symbol from Pyth.

Inputs:
- token_symbol: The asset ticker/symbol to fetch the price feed ID for (e.g. BTC, ETH, COIN, XAU, EUR)
- quote_currency: The quote currency to filter by (defaults to USD)
- asset_type: The asset type to search for (crypto, equity, fx, metal) - defaults to crypto

Examples:
- Crypto: BTC, ETH, SOL
- Equities: COIN, AAPL, TSLA
- FX: EUR, GBP, JPY
- Metals: XAU (Gold), XAG (Silver), XPT (Platinum), XPD (Palladium)
"""
    args_schema: ArgsSchema | None = FetchPriceFeedInput

    async def _arun(
        self,
        token_symbol: str,
        quote_currency: str = "USD",
        asset_type: str = "crypto",
    ) -> str:
        """Fetch the price feed ID for a given token symbol from Pyth.

        Args:
            token_symbol: The asset ticker/symbol to fetch the price feed ID for.
            quote_currency: The quote currency to filter by.
            asset_type: The asset type to search for.

        Returns:
            JSON string with the price feed ID or error details.
        """
        url = f"https://hermes.pyth.network/v2/price_feeds?query={token_symbol}&asset_type={asset_type}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)

                if response.status_code != 200:
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"HTTP error! status: {response.status_code}",
                        }
                    )

                data = response.json()

                if not data:
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"No price feed found for {token_symbol}",
                        }
                    )

                # Filter data by token symbol and quote currency
                filtered_data = [
                    item
                    for item in data
                    if (
                        item["attributes"]["base"].lower() == token_symbol.lower()
                        and item["attributes"]["quote_currency"].lower()
                        == quote_currency.lower()
                    )
                ]

                if not filtered_data:
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"No price feed found for {token_symbol}/{quote_currency}",
                        }
                    )

                # For equities, select the regular feed over special market hours feeds
                selected_feed = filtered_data[0]
                if asset_type == "equity":
                    # Look for regular market feed (no PRE, POST, ON, EXT suffixes)
                    regular_market_feed = next(
                        (
                            item
                            for item in filtered_data
                            if not any(
                                suffix in item["attributes"]["symbol"]
                                for suffix in [".PRE", ".POST", ".ON", ".EXT"]
                            )
                        ),
                        None,
                    )
                    if regular_market_feed:
                        selected_feed = regular_market_feed

                return json.dumps(
                    {
                        "success": True,
                        "priceFeedID": selected_feed["id"],
                        "tokenSymbol": token_symbol,
                        "quoteCurrency": quote_currency,
                        "feedType": selected_feed["attributes"]["display_symbol"],
                    }
                )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Error fetching price feed: {e!s}",
                }
            )
