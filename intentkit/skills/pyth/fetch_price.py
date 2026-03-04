"""Pyth fetch_price skill."""

import json

import httpx
from langchain_core.tools import ArgsSchema
from pydantic import BaseModel, Field

from intentkit.skills.pyth.base import PythBaseTool


class FetchPriceInput(BaseModel):
    """Input schema for fetching Pyth price."""

    price_feed_id: str = Field(..., description="Pyth price feed ID")


class PythFetchPrice(PythBaseTool):
    """Fetch the price from a Pyth price feed.

    This tool queries the Pyth Hermes API to get the current price
    for a given price feed ID.
    """

    name: str = "pyth_fetch_price"
    description: str = "Fetch price from a Pyth price feed by ID. Use pyth_fetch_price_feed first to get the feed ID from a ticker symbol."
    args_schema: ArgsSchema | None = FetchPriceInput

    async def _arun(
        self,
        price_feed_id: str,
    ) -> str:
        """Fetch price from Pyth for the given price feed ID.

        Args:
            price_feed_id: The price feed ID to fetch the price for.

        Returns:
            JSON string with the price or error details.
        """
        url = (
            f"https://hermes.pyth.network/v2/updates/price/latest?ids[]={price_feed_id}"
        )

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
                parsed_data = data.get("parsed", [])

                if not parsed_data:
                    return json.dumps(
                        {
                            "success": False,
                            "error": f"No price data found for {price_feed_id}",
                        }
                    )

                price_info = parsed_data[0]["price"]
                price = int(price_info["price"])
                exponent = price_info["expo"]

                # Format price
                if exponent < 0:
                    adjusted_price = price * 100
                    divisor = 10 ** (-exponent)
                    scaled_price = adjusted_price // divisor
                    price_str = f"{scaled_price // 100}.{scaled_price % 100:02d}"
                    formatted_price = (
                        price_str if not price_str.startswith(".") else f"0{price_str}"
                    )
                else:
                    scaled_price = price // (10**exponent)
                    formatted_price = str(scaled_price)

                return json.dumps(
                    {
                        "success": True,
                        "priceFeedID": price_feed_id,
                        "price": formatted_price,
                    }
                )

        except Exception as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Error fetching price from Pyth: {e!s}",
                }
            )
