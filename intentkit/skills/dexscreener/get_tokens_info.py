import logging
from typing import Any, List, Type

from pydantic import BaseModel, Field, ValidationError, field_validator

from intentkit.skills.dexscreener.base import DexScreenerBaseTool
from intentkit.skills.dexscreener.model.search_token_response import (
    SearchTokenResponseModel,
)
from intentkit.skills.dexscreener.utils import (
    API_ENDPOINTS,
    MAX_TOKENS_BATCH,
    RATE_LIMITS,
    create_error_response,
    create_no_results_response,
    format_success_response,
    get_liquidity_value,
    group_pairs_by_token,
    handle_validation_error,
    truncate_large_fields,
)

logger = logging.getLogger(__name__)


class GetTokensInfoInput(BaseModel):
    """Input schema for the DexScreener get_tokens_info tool."""

    chain_id: str = Field(
        description="The blockchain chain ID (e.g., 'ethereum', 'solana', 'bsc', 'polygon', 'arbitrum', 'base', 'avalanche')"
    )
    token_addresses: List[str] = Field(
        description=f"List of token contract addresses to retrieve info for (maximum {MAX_TOKENS_BATCH} addresses). "
        "Each address should be in the format '0x1234...abcd' for Ethereum-based chains."
    )

    @field_validator("token_addresses")
    @classmethod
    def validate_token_addresses(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one token address is required")
        if len(v) > MAX_TOKENS_BATCH:
            raise ValueError(f"Maximum {MAX_TOKENS_BATCH} token addresses allowed")
        # Remove duplicates while preserving order
        seen = set()
        unique_addresses = []
        for addr in v:
            if addr not in seen:
                seen.add(addr)
                unique_addresses.append(addr)
        return unique_addresses


class GetTokensInfo(DexScreenerBaseTool):
    """
    Tool to get detailed information for multiple tokens at once on DexScreener.
    """

    name: str = "dexscreener_get_tokens_info"
    description: str = (
        f"Retrieves detailed trading pair information for multiple tokens (up to {MAX_TOKENS_BATCH}) "
        "using chain ID and a list of token addresses. For each token, returns all available "
        "trading pairs with price, volume, liquidity, market data, and DEX information. "
        "This is more efficient than making individual calls when you need info for multiple tokens. "
        "Use this tool for portfolio analysis or comparing multiple tokens at once."
    )
    args_schema: Type[BaseModel] = GetTokensInfoInput

    async def _arun(
        self,
        chain_id: str,
        token_addresses: List[str],
        **kwargs: Any,
    ) -> str:
        """Implementation to get information for multiple tokens."""

        # Apply rate limiting
        await self.user_rate_limit_by_category(
            user_id=f"{self.category}{self.name}",
            limit=RATE_LIMITS["tokens"],
            minutes=1,
        )

        logger.info(
            f"Executing DexScreener get_tokens_info tool with chain_id: '{chain_id}', "
            f"token_addresses: {len(token_addresses)} tokens"
        )

        try:
            # Construct API path - addresses are comma-separated
            addresses_param = ",".join(token_addresses)
            api_path = f"{API_ENDPOINTS['tokens']}/{chain_id}/{addresses_param}"

            data, error_details = await self._get(path=api_path)

            if error_details:
                return await self._handle_error_response(error_details)

            if not data:
                logger.error(f"No data returned for tokens on {chain_id}")
                return create_error_response(
                    error_type="empty_success",
                    message="API call returned empty success response.",
                    additional_data={
                        "chain_id": chain_id,
                        "token_addresses": token_addresses,
                    },
                )

            try:
                # Validate response using SearchTokenResponseModel since API returns similar structure
                result = SearchTokenResponseModel.model_validate(data)
            except ValidationError as e:
                return handle_validation_error(
                    e, f"{chain_id}/{len(token_addresses)} tokens", len(str(data))
                )

            if not result.pairs:
                return create_no_results_response(
                    f"{chain_id} - {len(token_addresses)} tokens",
                    reason="no trading pairs found for any of the specified tokens",
                    additional_data={
                        "chain_id": chain_id,
                        "requested_addresses": token_addresses,
                        "tokens_data": {},
                        "all_pairs": [],
                        "found_tokens": 0,
                        "total_pairs": 0,
                    },
                )

            pairs_list = [p for p in result.pairs if p is not None]

            if not pairs_list:
                return create_no_results_response(
                    f"{chain_id} - {len(token_addresses)} tokens",
                    reason="all pairs were null or invalid",
                    additional_data={
                        "chain_id": chain_id,
                        "requested_addresses": token_addresses,
                        "tokens_data": {},
                        "all_pairs": [],
                        "found_tokens": 0,
                        "total_pairs": 0,
                    },
                )

            # Group pairs by token address for better organization
            tokens_data = group_pairs_by_token(pairs_list)

            # Sort pairs within each token by liquidity (highest first)
            for token_addr, pairs in tokens_data.items():
                try:
                    pairs.sort(key=get_liquidity_value, reverse=True)
                except Exception as sort_err:
                    logger.warning(
                        f"Failed to sort pairs for token {token_addr}: {sort_err}"
                    )

            logger.info(
                f"Found {len(pairs_list)} total pairs across {len(tokens_data)} tokens "
                f"for {len(token_addresses)} requested addresses on {chain_id}"
            )

            return format_success_response(
                {
                    "tokens_data": {
                        addr: [p.model_dump() for p in pairs]
                        for addr, pairs in tokens_data.items()
                    },
                    "all_pairs": [p.model_dump() for p in pairs_list],
                    "chain_id": chain_id,
                    "requested_addresses": token_addresses,
                    "found_tokens": len(tokens_data),
                    "total_pairs": len(pairs_list),
                }
            )

        except Exception as e:
            return await self._handle_unexpected_runtime_error(
                e, f"{chain_id}/{len(token_addresses)} tokens"
            )

    async def _handle_error_response(self, error_details: dict) -> str:
        """Formats error details (from _get) into a JSON string."""
        if error_details.get("error_type") in [
            "connection_error",
            "parsing_error",
            "unexpected_error",
        ]:
            logger.error(
                f"DexScreener get_tokens_info tool encountered an error: {error_details}"
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
            f"An unexpected runtime error occurred in get_tokens_info tool _arun method for {query_info}: {e}"
        )
        return create_error_response(
            error_type="runtime_error",
            message="An unexpected internal error occurred processing the tokens info request",
            details=str(e),
            additional_data={"query_info": query_info},
        )
