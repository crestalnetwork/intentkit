import json
import logging
from typing import Any, Dict, List, Optional, Type

import httpx
from pydantic import BaseModel, Field

from intentkit.skills.dapplooker.base import DappLookerBaseTool

logger = logging.getLogger(__name__)


class DappLookerTokenDataInput(BaseModel):
    """Input for DappLooker token data tool."""

    token_tickers: Optional[str] = Field(
        description="Comma-separated list of AI agent token tickers (e.g., 'aixbt,vader'). "
        "Either token_tickers or token_addresses must be provided.",
        default=None,
    )
    token_addresses: Optional[str] = Field(
        description="Comma-separated list of AI agent token contract addresses (e.g., '0x4F9Fd6Be4a90f2620860d680c0d4d5Fb53d1A825'). "
        "Either token_tickers or token_addresses must be provided.",
        default=None,
    )
    chain: str = Field(
        description="Blockchain network to query (e.g., 'base', 'ethereum').",
        default="base",
    )


class DappLookerTokenData(DappLookerBaseTool):
    """Tool for retrieving AI agent token data from DappLooker.

    This tool uses DappLooker's API to fetch comprehensive crypto market data and analytics
    specifically for AI agent tokens.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "dapplooker_token_data"
    description: str = (
        "Retrieve detailed token market data and analytics for AI agent tokens using DappLooker. "
        "Use this tool when you need current information about AI-focused crypto tokens, "
        "including price, market cap, volume, technical indicators, holder insights, and developer activity.\n"
        "You can query by token ticker (e.g., 'aixbt', 'vader') or by token contract address. "
        "Note that this tool is specialized for AI agent tokens and may not return data for general cryptocurrencies like ETH, BTC, or SOL.\n"
        "Either token_tickers or token_addresses must be provided."
    )
    args_schema: Type[BaseModel] = DappLookerTokenDataInput

    async def _arun(
        self,
        token_tickers: Optional[str] = None,
        token_addresses: Optional[str] = None,
        chain: str = "base",
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
        context = self.get_context()
        logger.debug(
            f"dapplooker_token_data.py: Fetching token data with context {context}"
        )

        # Get the API key from the agent's configuration or environment variable
        api_key = self.get_api_key()
        if not api_key:
            return "Error: No DappLooker API key provided in the configuration or environment."

        # Validate input
        if not token_tickers and not token_addresses:
            return "Error: Either token_tickers or token_addresses must be provided."

        # Check for common non-AI agent tokens that won't be in the database
        # Only check if using token_tickers, not relevant for token_addresses
        if (
            token_tickers
            and not token_addresses
            and token_tickers.lower()
            in [
                "btc",
                "eth",
                "sol",
                "bitcoin",
                "ethereum",
                "solana",
                "bnb",
                "xrp",
                "ada",
                "doge",
            ]
        ):
            return (
                f"The token '{token_tickers}' is not an AI agent token and is not tracked by DappLooker. "
                f"DappLooker specializes in AI agent tokens like 'aixbt', 'vader', and other AI-focused crypto projects. "
                f"Please try querying for an AI agent token instead."
            )

        # Set up the request parameters
        params = {
            "api_key": api_key,
            "chain": chain,
        }

        # Add either token_tickers or token_addresses to the parameters
        if token_tickers:
            params["token_tickers"] = token_tickers
        if token_addresses:
            params["token_addresses"] = token_addresses

        logger.debug(f"dapplooker_token_data.py: Request params: {params}")

        # Call DappLooker API
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    "https://api.dapplooker.com/v1/crypto-market/",
                    params=params,
                )

                logger.debug(
                    f"dapplooker_token_data.py: API response status: {response.status_code}"
                )

                if response.status_code != 200:
                    logger.error(
                        f"dapplooker_token_data.py: Error from DappLooker API: {response.status_code} - {response.text}"
                    )
                    return f"Error retrieving token data: {response.status_code} - {response.text}"

                # Parse the API response
                response_json = response.json()
                logger.debug(
                    f"dapplooker_token_data.py: Response type: {type(response_json)}"
                )

                # Check if response is a string and try to parse it
                if isinstance(response_json, str):
                    try:
                        response_json = json.loads(response_json)
                        logger.debug(
                            "dapplooker_token_data.py: Parsed string response as JSON"
                        )
                    except json.JSONDecodeError as e:
                        logger.error(
                            f"dapplooker_token_data.py: Error parsing JSON: {e}"
                        )
                        return f"Error processing token data: {e}"

                # Extract the data array from the response
                # The API returns {"success": true, "data": [...]}
                if isinstance(response_json, dict) and "data" in response_json:
                    data = response_json["data"]
                    logger.debug(
                        f"dapplooker_token_data.py: Found data array with {len(data)} items"
                    )
                else:
                    data = response_json  # Fallback for backward compatibility
                    logger.debug(
                        "dapplooker_token_data.py: Using response as data (fallback)"
                    )

                logger.debug(
                    f"dapplooker_token_data.py: Received data type: {type(data)}"
                )

                if not data or data == []:
                    query_type = (
                        "tickers"
                        if token_tickers and not token_addresses
                        else "addresses"
                    )
                    query_value = token_tickers if token_tickers else token_addresses
                    return (
                        f"No results found for {query_type}: '{query_value}' on chain '{chain}'. "
                        f"This may be because:\n"
                        f"1. The token is not an AI agent token tracked by DappLooker\n"
                        f"2. The token ticker or address is incorrect\n"
                        f"3. The token exists on a different blockchain than '{chain}'\n\n"
                        f"DappLooker specializes in AI agent tokens like 'aixbt', 'vader', and other AI-focused crypto projects."
                    )

                # Format the results
                return self._format_token_data(data)

        except Exception as e:
            logger.error(
                f"dapplooker_token_data.py: Error retrieving token data: {e}",
                exc_info=True,
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

        # Ensure data is a list
        if not isinstance(data, list):
            # If data is a dict, wrap it in a list
            if isinstance(data, dict):
                data = [data]
            else:
                return f"Error: Unexpected data format received from API: {type(data)}"

        formatted_results = "# AI Agent Token Market Data\n\n"

        for token in data:
            # Ensure token is a dict
            if not isinstance(token, dict):
                logger.error(
                    f"dapplooker_token_data.py: Token is not a dictionary: {token}"
                )
                continue

            token_info = token.get("token_info", {})
            token_metrics = token.get("token_metrics", {})
            technical_indicators = token.get("technical_indicators", {})
            token_holder_insights = token.get("token_holder_insights", {})
            smart_money_insights = token.get("smart_money_insights", {})
            dev_wallet_insights = token.get("dev_wallet_insights", {})

            # Token basic info
            name = token_info.get("name", "Unknown")
            symbol = token_info.get("symbol", "Unknown")
            chain = token_info.get("chain", "Unknown")
            address = token_info.get("ca", "Unknown")
            ecosystem = token_info.get("ecosystem", "Unknown")
            description = token_info.get("description", "")
            handle = token_info.get("handle", "Unknown")

            formatted_results += f"## {name} ({symbol})\n"
            formatted_results += f"Chain: {chain}\n"
            formatted_results += f"Ecosystem: {ecosystem}\n"
            formatted_results += f"Contract: {address}\n"
            if handle:
                formatted_results += f"Handle: {handle}\n"
            if description:
                formatted_results += f"Description: {description}\n"
            formatted_results += "\n"

            # Price and market metrics
            if token_metrics:
                formatted_results += "### Market Metrics\n"
                price = token_metrics.get("usd_price", "Unknown")
                mcap = token_metrics.get("mcap", "Unknown")
                fdv = token_metrics.get("fdv", "Unknown")
                volume_24h = token_metrics.get("volume_24h", "Unknown")
                total_liquidity = token_metrics.get("total_liquidity", "Unknown")

                formatted_results += f"Price: ${price}\n"
                formatted_results += f"Market Cap: ${mcap}\n"
                formatted_results += f"Fully Diluted Value: ${fdv}\n"
                formatted_results += f"24h Volume: ${volume_24h}\n"
                formatted_results += f"Total Liquidity: ${total_liquidity}\n"

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
                price_change_30d = token_metrics.get(
                    "price_change_percentage_30d", "Unknown"
                )

                formatted_results += f"Price Change 1h: {price_change_1h}%\n"
                formatted_results += f"Price Change 24h: {price_change_24h}%\n"
                formatted_results += f"Price Change 7d: {price_change_7d}%\n"
                formatted_results += f"Price Change 30d: {price_change_30d}%\n"

                # Volume and Market Cap changes
                volume_change_7d = token_metrics.get(
                    "volume_change_percentage_7d", "Unknown"
                )
                volume_change_30d = token_metrics.get(
                    "volume_change_percentage_30d", "Unknown"
                )
                mcap_change_7d = token_metrics.get(
                    "mcap_change_percentage_7d", "Unknown"
                )
                mcap_change_30d = token_metrics.get(
                    "mcap_change_percentage_30d", "Unknown"
                )

                formatted_results += f"Volume Change 7d: {volume_change_7d}%\n"
                formatted_results += f"Volume Change 30d: {volume_change_30d}%\n"
                formatted_results += f"Market Cap Change 7d: {mcap_change_7d}%\n"
                formatted_results += f"Market Cap Change 30d: {mcap_change_30d}%\n"

                # Price highs
                price_high_24h = token_metrics.get("price_high_24h", "Unknown")
                price_ath = token_metrics.get("price_ath", "Unknown")

                formatted_results += f"24h High: ${price_high_24h}\n"
                formatted_results += f"All-Time High: ${price_ath}\n\n"

            # Technical indicators
            if technical_indicators:
                formatted_results += "### Technical Indicators\n"
                support = technical_indicators.get("support", "Unknown")
                resistance = technical_indicators.get("resistance", "Unknown")
                rsi = technical_indicators.get("rsi", "Unknown")
                sma = technical_indicators.get("sma", "Unknown")

                formatted_results += f"Support: ${support}\n"
                formatted_results += f"Resistance: ${resistance}\n"
                formatted_results += f"RSI: {rsi}\n"
                formatted_results += f"SMA: ${sma}\n\n"

            # Token Holder Insights
            if token_holder_insights:
                formatted_results += "### Token Holder Insights\n"
                total_holders = token_holder_insights.get(
                    "total_holder_count", "Unknown"
                )
                holder_change_24h = token_holder_insights.get(
                    "holder_count_change_percentage_24h", "Unknown"
                )
                fifty_percent_wallets = token_holder_insights.get(
                    "fifty_percentage_holding_wallet_count", "Unknown"
                )

                # First 100 buyers metrics
                first_100_initial = token_holder_insights.get(
                    "first_100_buyers_initial_bought", "Unknown"
                )
                first_100_initial_pct = token_holder_insights.get(
                    "first_100_buyers_initial_bought_percentage", "Unknown"
                )
                first_100_current = token_holder_insights.get(
                    "first_100_buyers_current_holding", "Unknown"
                )
                first_100_current_pct = token_holder_insights.get(
                    "first_100_buyers_current_holding_percentage", "Unknown"
                )

                # Top holders concentration
                top_10_balance = token_holder_insights.get(
                    "top_10_holder_balance", "Unknown"
                )
                top_10_pct = token_holder_insights.get(
                    "top_10_holder_percentage", "Unknown"
                )
                top_50_balance = token_holder_insights.get(
                    "top_50_holder_balance", "Unknown"
                )
                top_50_pct = token_holder_insights.get(
                    "top_50_holder_percentage", "Unknown"
                )
                top_100_balance = token_holder_insights.get(
                    "top_100_holder_balance", "Unknown"
                )
                top_100_pct = token_holder_insights.get(
                    "top_100_holder_percentage", "Unknown"
                )

                if total_holders != "Unknown":
                    formatted_results += f"Total Holders: {total_holders}\n"
                formatted_results += f"Holder Change 24h: {holder_change_24h}%\n"
                if fifty_percent_wallets != "Unknown":
                    formatted_results += (
                        f"Wallets Holding 50%: {fifty_percent_wallets}\n"
                    )

                formatted_results += f"First 100 Buyers Initial: {first_100_initial} ({first_100_initial_pct}%)\n"
                formatted_results += f"First 100 Buyers Current: {first_100_current} ({first_100_current_pct}%)\n"

                formatted_results += (
                    f"Top 10 Holders: {top_10_balance} ({top_10_pct}%)\n"
                )
                formatted_results += (
                    f"Top 50 Holders: {top_50_balance} ({top_50_pct}%)\n"
                )
                formatted_results += (
                    f"Top 100 Holders: {top_100_balance} ({top_100_pct}%)\n\n"
                )

            # Smart money insights
            if smart_money_insights:
                formatted_results += "### Smart Money Insights\n"
                top_buys = smart_money_insights.get("top_25_holder_buy_24h", "Unknown")
                top_sells = smart_money_insights.get(
                    "top_25_holder_sold_24h", "Unknown"
                )

                formatted_results += f"Top 25 Holders Buy 24h: {top_buys}\n"
                formatted_results += f"Top 25 Holders Sell 24h: {top_sells}\n\n"

            # Developer Wallet Insights
            if dev_wallet_insights:
                formatted_results += "### Developer Wallet Insights\n"
                wallet_address = dev_wallet_insights.get("wallet_address", "Unknown")
                wallet_balance = dev_wallet_insights.get("wallet_balance", "Unknown")
                wallet_percentage = dev_wallet_insights.get(
                    "dev_wallet_total_holding_percentage", "Unknown"
                )
                outflow_txs = dev_wallet_insights.get(
                    "dev_wallet_outflow_txs_count_24h", "Unknown"
                )
                outflow_amount = dev_wallet_insights.get(
                    "dev_wallet_outflow_amount_24h", "Unknown"
                )
                fresh_wallet = dev_wallet_insights.get("fresh_wallet", False)
                dev_sold = dev_wallet_insights.get("dev_sold", False)
                dev_sold_percentage = dev_wallet_insights.get(
                    "dev_sold_percentage", "Unknown"
                )
                bundle_wallet_count = dev_wallet_insights.get(
                    "bundle_wallet_count", "Unknown"
                )
                bundle_wallet_supply = dev_wallet_insights.get(
                    "bundle_wallet_supply_percentage", "Unknown"
                )

                formatted_results += f"Developer Wallet: {wallet_address}\n"
                if wallet_balance != "Unknown":
                    formatted_results += f"Wallet Balance: {wallet_balance}\n"
                if wallet_percentage != "Unknown":
                    formatted_results += f"Wallet Holding %: {wallet_percentage}%\n"
                if outflow_txs != "Unknown":
                    formatted_results += f"Outflow Txs 24h: {outflow_txs}\n"
                if outflow_amount != "Unknown":
                    formatted_results += f"Outflow Amount 24h: {outflow_amount}\n"
                formatted_results += f"Fresh Wallet: {fresh_wallet}\n"
                formatted_results += f"Dev Has Sold: {dev_sold}\n"
                formatted_results += f"Dev Sold %: {dev_sold_percentage}%\n"
                formatted_results += f"Bundle Wallet Count: {bundle_wallet_count}\n"
                formatted_results += f"Bundle Supply %: {bundle_wallet_supply}%\n\n"

            # Supply information
            if token_metrics:
                formatted_results += "### Supply Information\n"
                circ_supply = token_metrics.get("circulating_supply", "Unknown")
                total_supply = token_metrics.get("total_supply", "Unknown")

                formatted_results += f"Circulating Supply: {circ_supply}\n"
                formatted_results += f"Total Supply: {total_supply}\n\n"

            # Last Updated
            last_updated = token.get("last_updated_at", "Unknown")
            if last_updated != "Unknown":
                formatted_results += f"Last Updated: {last_updated}\n\n"

            # Add separator between tokens
            formatted_results += "---\n\n"

        return formatted_results.strip()
