import logging
from typing import Any, Dict, List, Optional, Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.dapplooker.base import DappLookerBaseTool

logger = logging.getLogger(__name__)


class DappLookerTokenDataInput(BaseModel):
    """Input for DappLooker token data tool."""

    token_tickers: Optional[str] = Field(
        description="Comma-separated list of token tickers (e.g., 'aixbt,vader'). "
        "Either token_tickers or token_addresses must be provided.",
        default=None,
    )
    token_addresses: Optional[str] = Field(
        description="Comma-separated list of token contract addresses (e.g., '0x4F9Fd6Be4a90f2620860d680c0d4d5Fb53d1A825'). "
        "Either token_tickers or token_addresses must be provided.",
        default=None,
    )
    chain: str = Field(
        description="Blockchain network to query (e.g., 'base', 'ethereum').",
        default="base",
    )


class DappLookerTokenData(DappLookerBaseTool):
    """Tool for retrieving token data from DappLooker.

    This tool uses DappLooker's API to fetch comprehensive crypto market data and analytics.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "dapplooker_token_data"
    description: str = (
        "Retrieve detailed token market data and analytics using DappLooker. "
        "Use this tool when you need current information about crypto tokens, "
        "including price, market cap, volume, technical indicators, and smart money insights.\n"
        "You can query by token ticker (e.g., 'aixbt') or by token contract address. "
        "Either token_tickers or token_addresses must be provided."
    )
    args_schema: Type[BaseModel] = DappLookerTokenDataInput

    async def _arun(
        self,
        token_tickers: Optional[str] = None,
        token_addresses: Optional[str] = None,
        chain: str = "base",
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Implementation of the DappLooker token data tool.

        Args:
            token_tickers: Comma-separated list of token tickers.
            token_addresses: Comma-separated list of token contract addresses.
            chain: Blockchain network to query.
            config: The configuration for the tool call.

        Returns:
            str: Formatted token data with market metrics and analytics.
        """
        context = self.context_from_config(config)
        logger.debug(f"dapplooker.py: Fetching token data with context {context}")

        # Get the API key from the agent's configuration or environment variable
        api_key = self.get_api_key(context)
        if not api_key:
            return "Error: No DappLooker API key provided in the configuration or environment."

        # Validate input
        if not token_tickers and not token_addresses:
            return "Error: Either token_tickers or token_addresses must be provided."

        # Set up the request parameters
        params = {
            "api_key": api_key,
            "chain": chain,
        }

        if token_tickers:
            params["token_tickers"] = token_tickers
        elif token_addresses:
            params["token_addresses"] = token_addresses

        # Call DappLooker API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://api.0xloky.com/v1/crypto-market/",
                    params=params,
                )

                if response.status_code != 200:
                    logger.error(
                        f"dapplooker.py: Error from DappLooker API: {response.status_code} - {response.text}"
                    )
                    return f"Error retrieving token data: {response.status_code} - {response.text}"

                data = response.json()

                if not data:
                    query_type = "tickers" if token_tickers else "addresses"
                    query_value = token_tickers or token_addresses
                    return f"No results found for {query_type}: '{query_value}' on chain '{chain}'"

                # Format the results
                return self._format_token_data(data)

        except Exception as e:
            logger.error(
                f"dapplooker.py: Error retrieving token data: {e}", exc_info=True
            )
            return (
                "An error occurred while retrieving token data. Please try again later."
            )

    def _format_token_data(self, data: List[Dict[str, Any]]) -> str:
        """Format the token data for display.

        Args:
            data: List of token data dictionaries from DappLooker API.

        Returns:
            str: Formatted token data.
        """
        if not data:
            return "No token data available."

        formatted_results = "# Token Market Data\n\n"

        for token in data:
            token_info = token.get("token_info", {})
            token_metrics = token.get("token_metrics", {})
            technical_indicators = token.get("technical_indicators", {})
            smart_money_insights = token.get("smart_money_insights", {})

            # Token basic info
            name = token_info.get("name", "Unknown")
            symbol = token_info.get("symbol", "Unknown")
            chain = token_info.get("chain", "Unknown")
            address = token_info.get("ca", "Unknown")

            formatted_results += f"## {name} ({symbol})\n"
            formatted_results += f"**Chain:** {chain}\n"
            formatted_results += f"**Contract:** {address}\n\n"

            # Price and market metrics
            if token_metrics:
                formatted_results += "### Market Metrics\n"
                price = token_metrics.get("usd_price", "Unknown")
                mcap = token_metrics.get("mcap", "Unknown")
                fdv = token_metrics.get("fdv", "Unknown")
                volume_24h = token_metrics.get("volume_24h", "Unknown")

                formatted_results += f"**Price:** ${price}\n"
                formatted_results += f"**Market Cap:** ${mcap}\n"
                formatted_results += f"**Fully Diluted Value:** ${fdv}\n"
                formatted_results += f"**24h Volume:** ${volume_24h}\n"

                # Price changes
                price_change_1h = token_metrics.get(
                    "price_change_percentage_1h", "Unknown"
                )
                price_change_24h = token_metrics.get(
                    "price_change_percentage_24h", "Unknown"
                )
                price_change_7d = token_metrics.get(
                    "price_change_percentage_7d", "Unknown"
                )

                formatted_results += f"**Price Change 1h:** {price_change_1h}%\n"
                formatted_results += f"**Price Change 24h:** {price_change_24h}%\n"
                formatted_results += f"**Price Change 7d:** {price_change_7d}%\n\n"

            # Technical indicators
            if technical_indicators:
                formatted_results += "### Technical Indicators\n"
                support = technical_indicators.get("support", "Unknown")
                resistance = technical_indicators.get("resistance", "Unknown")
                rsi = technical_indicators.get("rsi", "Unknown")
                sma = technical_indicators.get("sma", "Unknown")

                formatted_results += f"**Support:** ${support}\n"
                formatted_results += f"**Resistance:** ${resistance}\n"
                formatted_results += f"**RSI:** {rsi}\n"
                formatted_results += f"**SMA:** ${sma}\n\n"

            # Smart money insights
            if smart_money_insights:
                formatted_results += "### Smart Money Insights\n"
                holder_count = smart_money_insights.get("total_holder_count", "Unknown")
                liquidity = smart_money_insights.get("total_liquidity", "Unknown")
                holder_change = smart_money_insights.get(
                    "holder_count_change_percentage_24h", "Unknown"
                )

                formatted_results += f"**Total Holders:** {holder_count}\n"
                formatted_results += f"**Total Liquidity:** ${liquidity}\n"
                formatted_results += f"**Holder Change 24h:** {holder_change}%\n"

                top_buys = smart_money_insights.get("top_25_holder_buy_24h", "Unknown")
                top_sells = smart_money_insights.get(
                    "top_25_holder_sold_24h", "Unknown"
                )

                formatted_results += f"**Top 25 Holders Buy 24h:** ${top_buys}\n"
                formatted_results += f"**Top 25 Holders Sell 24h:** ${top_sells}\n\n"

            # Supply information
            if token_metrics:
                formatted_results += "### Supply Information\n"
                circ_supply = token_metrics.get("circulating_supply", "Unknown")
                total_supply = token_metrics.get("total_supply", "Unknown")

                formatted_results += f"**Circulating Supply:** {circ_supply}\n"
                formatted_results += f"**Total Supply:** {total_supply}\n\n"

            # Add separator between tokens
            formatted_results += "---\n\n"

        return formatted_results.strip()
