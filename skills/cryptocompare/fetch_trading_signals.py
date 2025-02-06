"""Tool for fetching trading signals via CryptoCompare API."""

import asyncio
from typing import Any, Dict, Type
from pydantic import BaseModel
from skills.cryptocompare.base import CryptoCompareBaseTool
from skills.cryptocompare.api import fetch_trading_signals, FetchTradingSignalsInput

class CryptoCompareFetchTradingSignalsOutput(BaseModel):
    result: Dict[str, Any]
    error: str | None = None

class CryptoCompareFetchTradingSignals(CryptoCompareBaseTool):
    name: str = "cryptocompare_fetch_trading_signals"
    description: str = "Fetch trading signals for a cryptocurrency using CryptoCompare API"
    args_schema: Type[BaseModel] = FetchTradingSignalsInput

    def _run(self) -> CryptoCompareFetchTradingSignalsOutput:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> CryptoCompareFetchTradingSignalsOutput:
        input_data: FetchTradingSignalsInput = self.args
        is_rate_limited, error_msg = await self.check_rate_limit()
        if is_rate_limited:
            return CryptoCompareFetchTradingSignalsOutput(result={}, error=error_msg)
        try:
            result = await asyncio.to_thread(fetch_trading_signals, input_data.from_symbol)
            return CryptoCompareFetchTradingSignalsOutput(result=result)
        except Exception as e:
            return CryptoCompareFetchTradingSignalsOutput(result={}, error=str(e))

