"""Skill to fetch quantitative metrics for BTC or ETH from TokenMetrics API."""

from typing import Literal, Type

import httpx
from langchain.tools.base import ToolException
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from .base import TokenMetricsBaseTool, base_url


class TokenMetricsQuantInput(BaseModel):
    """Input schema for fetching quantitative metrics."""

    token_symbol: Literal["BTC", "ETH"] = Field(description="Token symbol (BTC or ETH)")


class QuantData(BaseModel):
    """Data model for quantitative metrics response."""

    token_id: int = Field(description="Token ID")
    token_name: str = Field(description="Token name")
    token_symbol: str = Field(description="Token symbol")
    date: str = Field(description="Data date")
    volatility: float = Field(description="Volatility")
    all_time_return: float = Field(description="All-time return")
    cagr: float = Field(description="Compound Annual Growth Rate")
    sharpe: float = Field(description="Sharpe Ratio")
    sortino: float = Field(description="Sortino Ratio")
    max_drawdown: float = Field(description="Maximum Drawdown")
    daily_value_at_risk: float = Field(description="Daily Value at Risk")
    profit_factor: float = Field(description="Profit Factor")


class TokenMetricsQuantOutput(BaseModel):
    """Output schema for fetching quantitative metrics."""

    data: QuantData
    summary: str = Field(description="Summary of the quant metrics")


class FetchQuantData(TokenMetricsBaseTool):
    """Skill to fetch quantitative metrics for BTC or ETH from TokenMetrics API."""

    name: str = "fetch_quant_data"
    description: str = (
        "Fetches quantitative metrics for BTC or ETH from TokenMetrics API."
    )
    args_schema: Type[BaseModel] = TokenMetricsQuantInput

    async def fetch_quant_metrics(self, token_symbol: str, api_key: str) -> QuantData:
        """Fetch quantitative metrics from TokenMetrics API.

        Args:
            token_symbol: Token symbol (BTC or ETH).
            api_key: TokenMetrics API key.

        Returns:
            QuantData containing the token's quantitative metrics.

        Raises:
            ToolException: If the API request fails or data is invalid.
        """
        token_id_map = {"BTC": 3375, "ETH": 3367}
        token_id = token_id_map.get(token_symbol)
        if not token_id:
            raise ToolException(f"Unsupported token symbol: {token_symbol}")

        url = f"{base_url}quant-metrics?token_id={token_id}"
        headers = {"accept": "application/json", "api_key": api_key}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()["data"][0]
                return QuantData(
                    token_id=data["TOKEN_ID"],
                    token_name=data["TOKEN_NAME"],
                    token_symbol=data["TOKEN_SYMBOL"],
                    date=data["DATE"],
                    volatility=data["VOLATILITY"],
                    all_time_return=data["ALL_TIME_RETURN"],
                    cagr=data["CAGR"],
                    sharpe=data["SHARPE"],
                    sortino=data["SORTINO"],
                    max_drawdown=data["MAX_DRAWDOWN"],
                    daily_value_at_risk=data["DAILY_VALUE_AT_RISK"],
                    profit_factor=data["PROFIT_FACTOR"],
                )
            except (httpx.RequestError, httpx.HTTPStatusError, KeyError) as e:
                raise ToolException(
                    f"Error fetching quant metrics from TokenMetrics: {e}"
                )

    async def _arun(self, token_symbol: str, config: RunnableConfig, **kwargs):
        """Async execution for fetching quantitative metrics.

        Args:
            token_symbol: Token symbol (BTC or ETH).
            config: Runnable configuration.
            **kwargs: Additional keyword arguments.

        Returns:
            TokenMetricsQuantOutput with quant data and summary.

        Raises:
            ToolException: If the API key is missing or request fails.
        """
        context = self.context_from_config(config)
        api_key = self.get_api_key(context)
        if not api_key:
            raise ToolException("TokenMetrics API key not found")

        quant_data = await self.fetch_quant_metrics(token_symbol, api_key)
        summary = (
            f"Quantitative metrics for {quant_data.token_name} ({token_symbol}): "
            f"Volatility={quant_data.volatility:.2f}, Sharpe={quant_data.sharpe:.2f}, "
            f"Sortino={quant_data.sortino:.2f}"
        )

        return TokenMetricsQuantOutput(data=quant_data, summary=summary)

    def _run(self, question: str):
        raise NotImplementedError("Use _arun for async execution")
