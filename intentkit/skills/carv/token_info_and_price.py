import logging
import re
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field

from intentkit.skills.carv.base import CarvBaseTool

logger = logging.getLogger(__name__)


class TokenInfoAndPriceInput(BaseModel):
    ticker: str = Field(
        description="The token's ticker symbol (e.g., 'eth', 'btc', 'sol', 'xrp')."
    )
    token_name: str = Field(
        description="The token name (e.g ethereum, bitcoin, solana, ripple)"
    )
    amount: Optional[float] = Field(
        description="(optional) amount of token, fill this if user asking for how much x amount of specific token worth"
    )


class TokenInfoAndPriceTool(CarvBaseTool):
    """
    Fetches detailed information and the current USD price of a cryptocurrency token from the CARV API,
    given its ticker symbol (e.g., 'eth', 'btc', 'aave').
    Returns metadata including the token's name, symbol, platform, category tags, and contract addresses
    Useful for understanding a token's identity, ecosystem, and market valu
    Use this tool when you need comprehensive token data and live pricing from CARV
    """

    name: str = "carv_token_info_and_price"
    description: str = (
        "Fetches detailed information and the current USD price of a cryptocurrency token from the CARV API, "
        "given its ticker symbol (e.g., 'eth', 'btc', 'aave'). or token name"
        "Returns metadata including the token's name, symbol, platform, category tags, and contract addresses "
        "Useful for understanding a token's identity, ecosystem, and market value"
        "Use this tool when you need comprehensive token data and live pricing from CARV."
    )
    args_schema: Type[BaseModel] = TokenInfoAndPriceInput

    async def _arun(
        self,
        ticker: str,
        token_name: str,
        amount: Optional[float] = 1,  # type: ignore
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if not ticker:
            return {
                "error": True,
                "message": "ticker is null",
                "suggestion": "ask the user for the specific ticker, and fill the `ticker` field when calling this tool",
            }

        context = self.get_context()
        params = {"ticker": ticker}
        path = "/ai-agent-backend/token_info"
        method = "GET"

        result, error = await self._call_carv_api(
            context=context,
            endpoint=path,
            params=params,
            method=method,
        )

        if error is not None or result is None:
            logger.error(f"Error returned from CARV API: {error}")
            return {
                "error": True,
                "error_type": "APIError",
                "message": "Failed to fetch token info from CARV API.",
                "details": error,
            }

        # retry with token_name if price is 0 or missing
        if "price" not in result or result["price"] == 0:
            fallback_ticker = re.sub(r"\s+", "-", token_name.strip().lower())
            logger.info(
                f"Fallback triggered. Trying with fallback ticker: {fallback_ticker}"
            )

            fallback_params = {"ticker": fallback_ticker}
            result, error = await self._call_carv_api(
                context=context,
                endpoint=path,
                params=fallback_params,
                method=method,
            )

            if error is not None or result is None or result.get("price") == 0:
                logger.error(f"Fallback error returned from CARV API: {error}")
                return {
                    "error": True,
                    "error_type": "APIError",
                    "message": "Failed to fetch token info from CARV API with fallback.",
                    "details": error,
                }

        if "price" in result and amount is not None:
            return {
                "additional_info": f"{amount} {ticker.upper()} is worth ${round(amount * result['price'], 2)}",
                **result,
            }

        return result
