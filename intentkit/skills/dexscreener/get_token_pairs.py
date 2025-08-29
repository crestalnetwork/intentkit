import logging
from typing import Any, Type

from pydantic import BaseModel, Field, ValidationError

from intentkit.skills.dexscreener.base import DexScreenerBaseTool
from intentkit.skills.dexscreener.model.search_token_response import (
    SearchTokenResponseModel,
)
from intentkit.skills.dexscreener.utils import (
    API_ENDPOINTS,
    RATE_LIMITS,
    create_error_response,
    create_no_results_response,
    format_success_response,
    get_liquidity_value,
    handle_validation_error,
    truncate_large_fields,
)

logger = logging.getLogger(__name__)


class GetTokenPairsInput(BaseModel):
    """Input schema for the DexScreener get_token_pairs tool."""

    chain_id: str = Field(
        description="The blockchain chain ID (e.g., 'ethereum', 'solana', 'bsc', 'polygon', 'arbitrum', 'base', 'avalanche')"
    )
    token_address: str = Field(
        description="The token contract address (e.g., '0x1234...abcd' for Ethereum-based chains)"
    )


class GetTokenPairs(DexScreenerBaseTool):
    """
    Tool to get all trading pairs for a specific token on DexScreener.
    """

    name: str = "dexscreener_get_token_pairs"
    description: str = (
        "Finds all trading pairs for a specific token using chain ID and token address. "
        "Returns a list of all pools/pairs where this token is traded, including pair addresses, "
        "DEX information, liquidity, volume, and pricing data for each pair. "
        "Use this tool to analyze all available trading venues and liquidity sources for a specific token."
    )
    args_schema: Type[BaseModel] = GetTokenPairsInput

    async def _arun(
        self,
        chain_id: str,
        token_address: str,
        **kwargs: Any,
    ) -> str:
        """Implementation to get all pairs for a specific token."""

        # Apply rate limiting
        await self.user_rate_limit_by_category(
            user_id=f"{self.category}{self.name}",
            limit=RATE_LIMITS["token_pairs"],
            minutes=1,
        )

        logger.info(
            f"Executing DexScreener get_token_pairs tool with chain_id: '{chain_id}', "
            f"token_address: '{token_address}'"
        )

        try:
            # Construct API path
            api_path = f"{API_ENDPOINTS['token_pairs']}/{chain_id}/{token_address}"

            data, error_details = await self._get(path=api_path)

            if error_details:
                return await self._handle_error_response(error_details)

            if not data:
                logger.error(
                    f"No data returned for token {token_address} on {chain_id}"
                )
                return create_error_response(
                    error_type="empty_success",
                    message="API call returned empty success response.",
                    additional_data={
                        "chain_id": chain_id,
                        "token_address": token_address,
                    },
                )

            try:
                # Validate response using SearchTokenResponseModel since API returns similar structure
                result = SearchTokenResponseModel.model_validate(data)
            except ValidationError as e:
                return handle_validation_error(
                    e, f"{chain_id}/{token_address}", len(str(data))
                )

            if not result.pairs:
                return create_no_results_response(
                    f"{chain_id}/{token_address}",
                    reason="no trading pairs found for this token",
                )

            pairs_list = [p for p in result.pairs if p is not None]

            if not pairs_list:
                return create_no_results_response(
                    f"{chain_id}/{token_address}",
                    reason="all pairs were null or invalid",
                )

            # Sort pairs by liquidity (highest first) for better UX
            try:
                pairs_list.sort(key=get_liquidity_value, reverse=True)
            except Exception as sort_err:
                logger.warning(f"Failed to sort pairs by liquidity: {sort_err}")

            logger.info(
                f"Found {len(pairs_list)} pairs for token {token_address} on {chain_id}"
            )

            return format_success_response(
                {
                    "pairs": [p.model_dump() for p in pairs_list],
                    "chain_id": chain_id,
                    "token_address": token_address,
                    "total_pairs": len(pairs_list),
                }
            )

        except Exception as e:
            return await self._handle_unexpected_runtime_error(
                e, f"{chain_id}/{token_address}"
            )

    async def _handle_error_response(self, error_details: dict) -> str:
        """Formats error details (from _get) into a JSON string."""
        if error_details.get("error_type") in [
            "connection_error",
            "parsing_error",
            "unexpected_error",
        ]:
            logger.error(
                f"DexScreener get_token_pairs tool encountered an error: {error_details}"
            )
        else:  # api_error
            logger.warning(f"DexScreener API returned an error: {error_details}")

        # Truncate potentially large fields before returning to user/LLM
        truncated_details = truncate_large_fields(error_details)
        return format_success_response(truncated_details)

    async def _handle_unexpected_runtime_error(
        self, e: Exception, query_info: str
    ) -> str:
        """Formats unexpected runtime exception details into a JSON string."""
        logger.exception(
            f"An unexpected runtime error occurred in get_token_pairs tool _arun method for {query_info}: {e}"
        )
        return create_error_response(
            error_type="runtime_error",
            message="An unexpected internal error occurred processing the token pairs request",
            details=str(e),
            additional_data={"query_info": query_info},
        )
