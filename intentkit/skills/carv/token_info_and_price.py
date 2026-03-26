import logging
import re
from typing import Any

from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.skills.carv.base import CarvBaseTool

logger = logging.getLogger(__name__)


class TokenInfoAndPriceInput(BaseModel):
    ticker: str = Field(description="Token ticker symbol (e.g., 'eth', 'btc')")
    token_name: str = Field(description="Token name (e.g., 'ethereum', 'bitcoin')")
    amount: float | None = Field(
        description="Token amount for value calculation (optional)"
    )


class TokenInfoAndPriceTool(CarvBaseTool):
    """
    Fetches detailed information and the current USD price of a cryptocurrency token from the CARV API,
    given its ticker symbol (e.g., 'eth', 'btc', 'aave').
    Returns metadata including the token's name, symbol, platform, category tags, and contract addresses
    Useful for understanding a token's identity, ecosystem, and market value
    Use this tool when you need comprehensive token data and live pricing from CARV
    """

    name: str = "carv_token_info_and_price"
    description: str = (
        "Get token info and current USD price from CARV by ticker or name. "
        "Returns metadata including symbol, platform, tags, and contract addresses."
    )
    args_schema: ArgsSchema | None = TokenInfoAndPriceInput

    async def _arun(
        self,
        ticker: str,
        token_name: str,
        amount: float | None = 1,  # type: ignore
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not ticker:
            raise ToolException(
                "ticker is null. Please provide the specific ticker symbol."
            )

        context = self.get_context()
        params = {"ticker": ticker}
        path = "/ai-agent-backend/token_info"
        method = "GET"

        result = await self._call_carv_api(
            context=context,
            endpoint=path,
            params=params,
            method=method,
        )

        # retry with token_name if price is 0 or missing
        if "price" not in result or result["price"] == 0:
            fallback_ticker = re.sub(r"\s+", "-", token_name.strip().lower())
            logger.info(
                "Fallback triggered. Trying with fallback ticker: %s", fallback_ticker
            )

            fallback_params = {"ticker": fallback_ticker}
            try:
                result = await self._call_carv_api(
                    context=context,
                    endpoint=path,
                    params=fallback_params,
                    method=method,
                )
                if result.get("price") == 0:
                    raise ToolException(
                        "Failed to fetch token price from CARV API with fallback."
                    )
            except ToolException:
                raise

        if "price" in result and amount is not None:
            return {
                "additional_info": f"{amount} {ticker.upper()} is worth ${round(amount * result['price'], 2)}",
                **result,
            }

        return result
