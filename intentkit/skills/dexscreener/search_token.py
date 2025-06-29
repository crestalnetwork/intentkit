import json
import logging
from enum import Enum
from typing import (
    Any,
    Callable,
    Literal,
    Optional,
    Type,
)

from pydantic import BaseModel, Field, ValidationError

from intentkit.skills.dexscreener.base import DexScreenerBaseTool
from intentkit.skills.dexscreener.model.search_token_response import (
    PairModel,
    SearchTokenResponseModel,
)

logger = logging.getLogger(__name__)

MAX_RESULTS_LIMIT = 25  # limit to 25 pair entries
SEARCH_TOKEN_API_PATH = "/latest/dex/search"

# Define the allowed sort options, including multiple volume types
SortByOption = Literal["liquidity", "volume"]
VolumeTimeframeOption = Literal["24_hour", "6_hour", "1_hour", "5_minutes"]


class QueryType(str, Enum):
    TEXT = "TEXT"
    TICKER = "TICKER"
    ADDRESS = "ADDRESS"


# this will bring aloside with pairs information
DISCLAIMER_TEXT = {
    "disclaimer": (
        "Search results may include unofficial, duplicate, or potentially malicious tokens. "
        "If multiple unrelated tokens share a similar name or ticker, ask the user for the exact token address. "
        "If the correct token is not found, re-run the tool using the provided address. "
        "Also advise the user to verify the token's legitimacy via its official social links included in the result."
    )
}


class SearchTokenInput(BaseModel):
    """Input schema for the DexScreener search_token tool."""

    query: str = Field(
        description="The search query string (e.g., token symbol 'WIF', pair address, token address '0x...', token name 'Dogwifhat', or ticker '$WIF'). Prefixing with '$' filters results to match the base token symbol exactly (case-insensitive)."
    )
    sort_by: Optional[SortByOption] = Field(
        default="liquidity",
        description="Sort preference for the results. Options: 'liquidity' (default) or 'volume'",
    )
    volume_timeframe: Optional[VolumeTimeframeOption] = Field(
        default="24_hour",
        description=f"define which timeframe should we use if the 'sort_by' is `volume` avalable options are {VolumeTimeframeOption}",
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
        f"limited to the top {MAX_RESULTS_LIMIT}. "
        f"Use this tool to find token information based on user queries."
    )
    args_schema: Type[BaseModel] = SearchTokenInput

    async def _arun(
        self,
        query: str,
        sort_by: Optional[SortByOption] = "liquidity",
        volume_timeframe: Optional[VolumeTimeframeOption] = "24_hour",
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

        sort_by = sort_by or "liquidity"
        volume_timeframe = volume_timeframe or "24_hour"

        # Determine query type
        query_type = self.get_query_type(query)

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

        ### --- sort functions ---
        def get_liquidity_usd(pair: PairModel) -> float:
            return (
                pair.liquidity.usd
                if pair.liquidity and pair.liquidity.usd is not None
                else 0.0
            )

        def get_volume(pair: PairModel) -> float:
            if not pair.volume:
                return 0.0
            return {
                "24_hour": pair.volume.h24,
                "6_hour": pair.volume.h6,
                "1_hour": pair.volume.h1,
                "5_minutes": pair.volume.m5,
            }.get(volume_timeframe, 0.0) or 0.0

        def get_sort_key_func() -> Callable[[PairModel], float]:
            if sort_by == "liquidity":
                return get_liquidity_usd
            if sort_by == "volume":
                return get_volume
            logger.warning(
                f"Invalid sort_by value '{sort_by}', defaulting to liquidity."
            )
            return get_liquidity_usd

        ### --- END sort functions ---

        try:
            data, error_details = await self._get(
                path=SEARCH_TOKEN_API_PATH, params={"q": search_query}
            )

            if error_details:
                return await self._handle_error_response(error_details)
            if not data:
                logger.error(f"No data or error details returned for query '{query}'")
                return json.dumps(
                    {
                        "error": "API call returned empty success response.",
                        "error_type": "empty_success",
                    },
                    indent=2,
                )

            try:
                result = SearchTokenResponseModel.model_validate(data)
            except ValidationError as e:
                return await self._handle_validation_error(e, query, data)

            if not result.pairs:
                return await self._no_pairs_found_response(
                    query, reason="returned null or empty for pairs"
                )

            pairs_list = [p for p in result.pairs if p is not None]

            # Apply filtering based on query type
            if query_type == QueryType.TICKER and target_ticker:
                pairs_list = [
                    p
                    for p in pairs_list
                    if p.baseToken
                    and p.baseToken.symbol
                    and p.baseToken.symbol.upper() == target_ticker
                ]
                if not pairs_list:
                    return await self._no_pairs_found_response(
                        query, reason=f"no match for ticker '${target_ticker}'"
                    )
            elif query_type == QueryType.ADDRESS:
                # Filter by address (checking pairAddress, baseToken.address, quoteToken.address)
                pairs_list = [
                    p
                    for p in pairs_list
                    if (p.pairAddress and p.pairAddress.lower() == search_query.lower())
                    or (
                        p.baseToken
                        and p.baseToken.address
                        and p.baseToken.address.lower() == search_query.lower()
                    )
                    or (
                        p.quoteToken
                        and p.quoteToken.address
                        and p.quoteToken.address.lower() == search_query.lower()
                    )
                ]
                if not pairs_list:
                    return await self._no_pairs_found_response(
                        query, reason=f"no match for address '{search_query}'"
                    )

            try:
                sort_func = get_sort_key_func()
                pairs_list.sort(key=sort_func, reverse=True)
            except Exception as sort_err:
                logger.error(f"Sorting failed: {sort_err}", exc_info=True)
                return json.dumps(
                    {
                        "error": "Failed to sort results.",
                        "error_type": "sorting_error",
                        "details": str(sort_err),
                        "unsorted_results": [
                            p.model_dump() for p in pairs_list[:MAX_RESULTS_LIMIT]
                        ],
                        **DISCLAIMER_TEXT,
                    },
                    indent=2,
                )

            final_count = min(len(pairs_list), MAX_RESULTS_LIMIT)
            logger.info(f"Returning {final_count} pairs for query '{query}'")
            return json.dumps(
                {
                    **DISCLAIMER_TEXT,
                    "pairs": [p.model_dump() for p in pairs_list[:MAX_RESULTS_LIMIT]],
                },
                indent=2,
            )
        except Exception as e:
            return await self._handle_unexpected_runtime_error(e, query)

    def get_query_type(self, query: str) -> QueryType:
        """
        Determine whether the query is a TEXT, TICKER, or ADDRESS.

        TICKER: starts with '$'
        ADDRESS: starts with '0x'.
        TEXT: anything else.
        """
        if query.startswith("0x"):
            return QueryType.ADDRESS
        if query.startswith("$"):
            return QueryType.TICKER
        return QueryType.TEXT

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
        for key in ["details", "response_body"]:
            if (
                isinstance(error_details.get(key), str)
                and len(error_details[key]) > 500
            ):
                error_details[key] = error_details[key][:500] + "... (truncated)"

        return json.dumps(error_details, indent=2)

    async def _handle_validation_error(
        self, e: ValidationError, query: str, data: Any
    ) -> str:
        """Formats validation error details into a JSON string."""
        logger.error(
            f"Failed to validate DexScreener response structure for query '{query}'. Error: {e}. Raw data length: {len(str(data))}",
            exc_info=True,
        )
        # Avoid sending potentially huge raw data back
        return json.dumps(
            {
                "error": "Failed to parse successful DexScreener API response",
                "error_type": "validation_error",
                "details": e.errors(),
            },
            indent=2,
        )

    async def _handle_unexpected_runtime_error(self, e: Exception, query: str) -> str:
        """Formats unexpected runtime exception details into a JSON string."""
        logger.exception(
            f"An unexpected runtime error occurred in search_token tool _arun method for query '{query}': {e}"
        )
        return json.dumps(
            {
                "error": "An unexpected internal error occurred processing the search request",
                "error_type": "runtime_error",
                "details": str(e),
            },
            indent=2,
        )

    async def _no_pairs_found_response(
        self, query: str, reason: str = "returned no matching pairs"
    ) -> str:
        """Generates the standard 'no pairs found' JSON response."""
        logger.info(f"DexScreener search for query '{query}': {reason}.")
        return json.dumps(
            {
                "message": f"No matching pairs found for the query '{query}'. Reason: {reason}.",
                "query": query,
                "pairs": [],
            },
            indent=2,
        )
