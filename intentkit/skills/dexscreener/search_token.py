import logging
from typing import Any, Optional, Type

from pydantic import BaseModel, Field, ValidationError

from intentkit.skills.dexscreener.base import DexScreenerBaseTool
from intentkit.skills.dexscreener.model.search_token_response import (
    SearchTokenResponseModel,
)
from intentkit.skills.dexscreener.utils import (
    API_ENDPOINTS,
    MAX_SEARCH_RESULTS,
    SEARCH_DISCLAIMER,
    QueryType,
    SortBy,
    VolumeTimeframe,
    create_error_response,
    create_no_results_response,
    determine_query_type,
    filter_address_pairs,
    filter_ticker_pairs,
    format_success_response,
    handle_validation_error,
    sort_pairs_by_criteria,
    truncate_large_fields,
)

logger = logging.getLogger(__name__)


class SearchTokenInput(BaseModel):
    """Input schema for the DexScreener search_token tool."""

    query: str = Field(
        description="The search query string (e.g., token symbol 'WIF', pair address, token address '0x...', token name 'Dogwifhat', or ticker '$WIF'). Prefixing with '$' filters results to match the base token symbol exactly (case-insensitive)."
    )
    sort_by: Optional[SortBy] = Field(
        default=SortBy.LIQUIDITY,
        description="Sort preference for the results. Options: 'liquidity' (default) or 'volume'",
    )
    volume_timeframe: Optional[VolumeTimeframe] = Field(
        default=VolumeTimeframe.TWENTY_FOUR_HOUR,
        description="Define which timeframe should we use if the 'sort_by' is 'volume'. Available options: '5_minutes', '1_hour', '6_hour', '24_hour'",
    )


class SearchToken(DexScreenerBaseTool):
    """
    Tool to search for token pairs on DexScreener based on a query string.
    """

    name: str = "dexscreener_search_token"
    description: str = (
        f"Searches DexScreener for token pairs matching the provided query string "
        f"(e.g., token symbol like 'WIF', pair address, token name like 'Dogwifhat', or ticker like '$WIF'). "
        f"If the query starts with '$', it filters results to only include pairs where the base token symbol exactly matches the ticker (case-insensitive). "
        f"Returns a list of matching pairs with details like price, volume, liquidity, etc., "
        f"sorted by the specified criteria (via 'sort_by': 'liquidity', 'volume'; defaults to 'liquidity'), "
        f"limited to the top {MAX_SEARCH_RESULTS}. "
        f"Use this tool to find token information based on user queries."
    )
    args_schema: Type[BaseModel] = SearchTokenInput

    async def _arun(
        self,
        query: str,
        sort_by: Optional[SortBy] = SortBy.LIQUIDITY,
        volume_timeframe: Optional[VolumeTimeframe] = VolumeTimeframe.TWENTY_FOUR_HOUR,
        **kwargs: Any,
    ) -> str:
        """Implementation to search token, with filtering based on query type."""

        # dexscreener 300 request per minute (across all user) based on dexscreener docs
        # https://docs.dexscreener.com/api/reference#get-latest-dex-search
        await self.user_rate_limit_by_category(
            # using hardcoded user_id to make sure it limit across all users
            user_id=f"{self.category}{self.name}",
            limit=300,
            minutes=1,
        )

        sort_by = sort_by or SortBy.LIQUIDITY
        volume_timeframe = volume_timeframe or VolumeTimeframe.TWENTY_FOUR_HOUR

        # Determine query type
        query_type = determine_query_type(query)

        # Process query based on type
        if query_type == QueryType.TICKER:
            search_query = query[1:]  # Remove the '$' prefix
            target_ticker = search_query.upper()
        else:
            search_query = query
            target_ticker = None

        logger.info(
            f"Executing DexScreener search_token tool with query: '{query}' "
            f"(interpreted as {query_type.value} search for '{search_query}'), "
            f"sort_by: {sort_by}"
        )

        try:
            data, error_details = await self._get(
                path=API_ENDPOINTS["search"], params={"q": search_query}
            )

            if error_details:
                return await self._handle_error_response(error_details)
            if not data:
                logger.error(f"No data or error details returned for query '{query}'")
                return create_error_response(
                    error_type="empty_success",
                    message="API call returned empty success response.",
                    additional_data={"query": query},
                )

            try:
                result = SearchTokenResponseModel.model_validate(data)
            except ValidationError as e:
                return handle_validation_error(e, query, len(str(data)))

            if not result.pairs:
                return create_no_results_response(
                    query, reason="returned null or empty for pairs"
                )

            pairs_list = [p for p in result.pairs if p is not None]

            # Apply filtering based on query type
            if query_type == QueryType.TICKER and target_ticker:
                pairs_list = filter_ticker_pairs(pairs_list, target_ticker)
                if not pairs_list:
                    return create_no_results_response(
                        query, reason=f"no match for ticker '${target_ticker}'"
                    )
            elif query_type == QueryType.ADDRESS:
                pairs_list = filter_address_pairs(pairs_list, search_query)
                if not pairs_list:
                    return create_no_results_response(
                        query, reason=f"no match for address '{search_query}'"
                    )

            # Sort pairs by specified criteria
            pairs_list = sort_pairs_by_criteria(pairs_list, sort_by, volume_timeframe)

            # If sorting failed, pairs_list will be returned unchanged by the utility function

            final_count = min(len(pairs_list), MAX_SEARCH_RESULTS)
            logger.info(f"Returning {final_count} pairs for query '{query}'")
            return format_success_response(
                {
                    **SEARCH_DISCLAIMER,
                    "pairs": [p.model_dump() for p in pairs_list[:MAX_SEARCH_RESULTS]],
                }
            )
        except Exception as e:
            return await self._handle_unexpected_runtime_error(e, query)

    async def _handle_error_response(self, error_details: dict) -> str:
        """Formats error details (from _get) into a JSON string."""
        if error_details.get("error_type") in [
            "connection_error",
            "parsing_error",
            "unexpected_error",
        ]:
            logger.error(f"DexScreener tool encountered an error: {error_details}")
        else:  # api_error
            logger.warning(f"DexScreener API returned an error: {error_details}")

        # Truncate potentially large fields before returning to user/LLM
        truncated_details = truncate_large_fields(error_details)
        return format_success_response(truncated_details)

    async def _handle_unexpected_runtime_error(self, e: Exception, query: str) -> str:
        """Formats unexpected runtime exception details into a JSON string."""
        logger.exception(
            f"An unexpected runtime error occurred in search_token tool _arun method for query '{query}': {e}"
        )
        return create_error_response(
            error_type="runtime_error",
            message="An unexpected internal error occurred processing the search request",
            details=str(e),
            additional_data={"query": query},
        )
