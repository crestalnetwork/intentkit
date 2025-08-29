import logging
from typing import Any, Type

from pydantic import BaseModel, Field

from intentkit.skills.dexscreener.base import DexScreenerBaseTool
from intentkit.skills.dexscreener.model.search_token_response import PairModel
from intentkit.skills.dexscreener.utils import (
    API_ENDPOINTS,
    RATE_LIMITS,
    create_error_response,
    format_success_response,
    truncate_large_fields,
)

logger = logging.getLogger(__name__)


class GetPairInfoInput(BaseModel):
    """Input schema for the DexScreener get_pair_info tool."""

    chain_id: str = Field(
        description="The blockchain chain ID (e.g., 'ethereum', 'solana', 'bsc', 'polygon', 'arbitrum', 'base', 'avalanche')"
    )
    pair_address: str = Field(
        description="The trading pair contract address (e.g., '0x1234...abcd' for Ethereum-based chains)"
    )


class GetPairInfo(DexScreenerBaseTool):
    """
    Tool to get detailed information about a specific trading pair on DexScreener.
    """

    name: str = "dexscreener_get_pair_info"
    description: str = (
        "Retrieves detailed information about a specific trading pair using chain ID and pair address. "
        "Returns comprehensive data including current price, volume, liquidity, price changes, "
        "market cap, FDV, transaction counts, and social links. "
        "Use this tool when you have a specific pair address and need detailed trading metrics."
    )
    args_schema: Type[BaseModel] = GetPairInfoInput

    async def _arun(
        self,
        chain_id: str,
        pair_address: str,
        **kwargs: Any,
    ) -> str:
        """Implementation to get specific pair information."""

        # Apply rate limiting
        await self.user_rate_limit_by_category(
            user_id=f"{self.category}{self.name}",
            limit=RATE_LIMITS["pairs"],
            minutes=1,
        )

        logger.info(
            f"Executing DexScreener get_pair_info tool with chain_id: '{chain_id}', "
            f"pair_address: '{pair_address}'"
        )

        try:
            # Construct API path
            api_path = f"{API_ENDPOINTS['pairs']}/{chain_id}/{pair_address}"

            data, error_details = await self._get(path=api_path)

            if error_details:
                return await self._handle_error_response(error_details)

            if not data:
                logger.error(f"No data returned for pair {pair_address} on {chain_id}")
                return create_error_response(
                    error_type="empty_success",
                    message="API call returned empty success response.",
                    additional_data={
                        "chain_id": chain_id,
                        "pair_address": pair_address,
                    },
                )

            # The API returns a single pair object, not wrapped in a pairs array
            if not isinstance(data, dict):
                return create_error_response(
                    error_type="format_error",
                    message="Unexpected response format - expected object",
                    additional_data={
                        "chain_id": chain_id,
                        "pair_address": pair_address,
                    },
                )

            try:
                # Validate the response using our existing PairModel
                pair_data = PairModel.model_validate(data)
                logger.info(
                    f"Successfully retrieved pair info for {pair_address} on {chain_id}"
                )

                return format_success_response(
                    {
                        "pair": pair_data.model_dump(),
                        "chain_id": chain_id,
                        "pair_address": pair_address,
                    }
                )

            except Exception as validation_error:
                logger.error(
                    f"Failed to validate pair response for {pair_address} on {chain_id}: {validation_error}",
                    exc_info=True,
                )
                # Return raw data if validation fails
                return format_success_response(
                    {
                        "pair": data,
                        "chain_id": chain_id,
                        "pair_address": pair_address,
                        "validation_warning": "Response structure may have changed",
                    }
                )

        except Exception as e:
            return await self._handle_unexpected_runtime_error(
                e, f"{chain_id}/{pair_address}"
            )

    async def _handle_error_response(self, error_details: dict) -> str:
        """Formats error details (from _get) into a JSON string."""
        if error_details.get("error_type") in [
            "connection_error",
            "parsing_error",
            "unexpected_error",
        ]:
            logger.error(
                f"DexScreener get_pair_info tool encountered an error: {error_details}"
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
            f"An unexpected runtime error occurred in get_pair_info tool _arun method for {query_info}: {e}"
        )
        return create_error_response(
            error_type="runtime_error",
            message="An unexpected internal error occurred processing the pair info request",
            details=str(e),
            additional_data={"query_info": query_info},
        )
