"""Tool for fetching top cryptocurrencies by market cap via CryptoCompare API."""

import asyncio
from typing import Any, Dict, Type
from pydantic import BaseModel
from skills.cryptocompare.base import CryptoCompareBaseTool
from skills.cryptocompare.api import fetch_top_market_cap, FetchTopMarketCapInput

class CryptoCompareFetchTopMarketCapOutput(BaseModel):
    result: Dict[str, Any]
    error: str | None = None

class CryptoCompareFetchTopMarketCap(CryptoCompareBaseTool):
    name: str = "cryptocompare_fetch_top_market_cap"
    description: str = "Fetch top cryptocurrencies by market cap using CryptoCompare API"
    args_schema: Type[BaseModel] = FetchTopMarketCapInput

    def _run(self) -> CryptoCompareFetchTopMarketCapOutput:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> CryptoCompareFetchTopMarketCapOutput:
        input_data: FetchTopMarketCapInput = self.args
        is_rate_limited, error_msg = await self.check_rate_limit()
        if is_rate_limited:
            return CryptoCompareFetchTopMarketCapOutput(result={}, error=error_msg)
        try:
            result = await asyncio.to_thread(fetch_top_market_cap, input_data.limit, input_data.to_symbol)
            return CryptoCompareFetchTopMarketCapOutput(result=result)
        except Exception as e:
            return CryptoCompareFetchTopMarketCapOutput(result={}, error=str(e))

