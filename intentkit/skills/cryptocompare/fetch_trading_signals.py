"""Tool for fetching cryptocurrency trading signals via CryptoCompare API."""

import logging
from typing import Dict, List, Type

from pydantic import BaseModel, Field

from intentkit.skills.cryptocompare.base import CryptoCompareBaseTool

logger = logging.getLogger(__name__)


class CryptoCompareFetchTradingSignalsInput(BaseModel):
    """Input for CryptoCompareFetchTradingSignals tool."""

    from_symbol: str = Field(
        ...,
        description="Cryptocurrency symbol to fetch trading signals for (e.g., 'BTC')",
    )


class TradingSignal(BaseModel):
    """Model representing a cryptocurrency trading signal."""

    symbol: str
    indicator: str
    value: float
    signal: str
    description: str


class CryptoCompareFetchTradingSignals(CryptoCompareBaseTool):
    """Tool for fetching cryptocurrency trading signals from CryptoCompare.

    This tool uses the CryptoCompare API to retrieve the latest trading signals
    for a specific cryptocurrency. These signals can help inform trading decisions.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "cryptocompare_fetch_trading_signals"
    description: str = "Fetch the latest trading signals for a specific cryptocurrency"
    args_schema: Type[BaseModel] = CryptoCompareFetchTradingSignalsInput

    async def _arun(
        self,
        from_symbol: str,
        **kwargs,
    ) -> List[TradingSignal]:
        """Async implementation of the tool to fetch cryptocurrency trading signals.

        Args:
            from_symbol: Cryptocurrency symbol to fetch trading signals for (e.g., 'BTC')
            config: The configuration for the runnable, containing agent context.

        Returns:
            List[TradingSignal]: A list of trading signals for the specified cryptocurrency.

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

            # Fetch trading signals data directly
            signals_data = await self.fetch_trading_signals(api_key, from_symbol)

            # Check for errors
            if "error" in signals_data:
                raise ValueError(signals_data["error"])

            # Convert to list of TradingSignal objects
            result = []
            if "Data" in signals_data and signals_data["Data"]:
                for indicator_name, indicator_data in signals_data["Data"].items():
                    if (
                        isinstance(indicator_data, Dict)
                        and "sentiment" in indicator_data
                    ):
                        result.append(
                            TradingSignal(
                                symbol=from_symbol,
                                indicator=indicator_name,
                                value=indicator_data.get("score", 0.0),
                                signal=indicator_data.get("sentiment", ""),
                                description=indicator_data.get("description", ""),
                            )
                        )

            return result

        except Exception as e:
            logger.error("Error fetching trading signals: %s", str(e))
            raise type(e)(f"[agent:{context.agent_id}]: {e}") from e
