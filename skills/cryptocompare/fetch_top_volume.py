"""Tool for fetching top cryptocurrencies by trading volume via CryptoCompare API."""

import asyncio
from typing import Any, Dict, Type
from pydantic import BaseModel
from skills.cryptocompare.base import CryptoCompareBaseTool
from skills.cryptocompare.api import fetch_top_volume, FetchTopVolumeInput

class CryptoCompareFetchTopVolumeOutput(BaseModel):
    result: Dict[str, Any]
    error: str | None = None

class CryptoCompareFetchTopVolume(CryptoCompareBaseTool):
    name: str = "cryptocompare_fetch_top_volume"
    description: str = "Fetch top cryptocurrencies by trading volume using CryptoCompare API"
    args_schema: Type[BaseModel] = FetchTopVolumeInput

    def _run(self) -> CryptoCompareFetchTopVolumeOutput:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> CryptoCompareFetchTopVolumeOutput:
        input_data: FetchTopVolumeInput = self.args
        is_rate_limited, error_msg = await self.check_rate_limit()
        if is_rate_limited:
            return CryptoCompareFetchTopVolumeOutput(result={}, error=error_msg)
        try:
            result = await asyncio.to_thread(fetch_top_volume, input_data.limit, input_data.to_symbol)
            return CryptoCompareFetchTopVolumeOutput(result=result)
        except Exception as e:
            return CryptoCompareFetchTopVolumeOutput(result={}, error=str(e))

