"""Tool for fetching cryptocurrency prices via CryptoCompare API."""

import asyncio
from typing import Any, Dict, Type, List
from pydantic import BaseModel
from skills.cryptocompare.base import CryptoCompareBaseTool
from skills.cryptocompare.api import fetch_price, FetchPriceInput

class CryptoCompareFetchPriceOutput(BaseModel):
    result: Dict[str, Any]
    error: str | None = None

class CryptoCompareFetchPrice(CryptoCompareBaseTool):
    name: str = "cryptocompare_fetch_price"
    description: str = "Fetch cryptocurrency price data using CryptoCompare API"
    args_schema: Type[BaseModel] = FetchPriceInput

    def _run(self) -> CryptoCompareFetchPriceOutput:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> CryptoCompareFetchPriceOutput:
        input_data: FetchPriceInput = self.args
        is_rate_limited, error_msg = await self.check_rate_limit()
        if is_rate_limited:
            return CryptoCompareFetchPriceOutput(result={}, error=error_msg)
        try:
            result = await asyncio.to_thread(fetch_price, input_data.from_symbol, input_data.to_symbols)
            return CryptoCompareFetchPriceOutput(result=result)
        except Exception as e:
            return CryptoCompareFetchPriceOutput(result={}, error=str(e))

