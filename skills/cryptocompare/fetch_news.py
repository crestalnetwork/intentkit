"""Tool for fetching news via CryptoCompare API."""

import asyncio
from typing import Any, Dict, Type
from pydantic import BaseModel
from skills.cryptocompare.base import CryptoCompareBaseTool
from skills.cryptocompare.api import fetch_news, FetchNewsInput

class CryptoCompareFetchNewsOutput(BaseModel):
    result: Dict[str, Any]
    error: str | None = None

class CryptoCompareFetchNews(CryptoCompareBaseTool):
    name: str = "cryptocompare_fetch_news"
    description: str = "Fetch cryptocurrency news for a given token using CryptoCompare API"
    args_schema: Type[BaseModel] = FetchNewsInput

    def _run(self) -> CryptoCompareFetchNewsOutput:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> CryptoCompareFetchNewsOutput:
        input_data: FetchNewsInput = self.args
        is_rate_limited, error_msg = await self.check_rate_limit()
        if is_rate_limited:
            return CryptoCompareFetchNewsOutput(result={}, error=error_msg)
        try:
            result = await asyncio.to_thread(fetch_news, input_data.token, input_data.timestamp)
            return CryptoCompareFetchNewsOutput(result=result)
        except Exception as e:
            return CryptoCompareFetchNewsOutput(result={}, error=str(e))

