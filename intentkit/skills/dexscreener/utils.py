"""
Utility functions and constants for DexScreener skills.
"""

import json
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import ValidationError

from intentkit.skills.dexscreener.model.search_token_response import PairModel

logger = logging.getLogger(__name__)

# API Base URL
DEXSCREENER_BASE_URL = "https://api.dexscreener.com"

# API Endpoints
API_ENDPOINTS = {
    "search": "/latest/dex/search",
    "pairs": "/latest/dex/pairs",
    "token_pairs": "/token-pairs/v1",
    "tokens": "/tokens/v1",
    "token_profiles": "/token-profiles/latest/v1",
    "token_boosts_latest": "/token-boosts/latest/v1",
    "token_boosts_top": "/token-boosts/top/v1",
    "orders": "/orders/v1",
}

# Rate Limits (requests per minute)
RATE_LIMITS = {
    "search": 300,
    "pairs": 300,
    "token_pairs": 300,
    "tokens": 300,
    "token_profiles": 60,
    "token_boosts": 60,
    "orders": 60,
}

# Limits
MAX_SEARCH_RESULTS = 25
MAX_TOKENS_BATCH = 30

# Common disclaimer for search results
SEARCH_DISCLAIMER = {
    "disclaimer": (
        "Search results may include unofficial, duplicate, or potentially malicious tokens. "
        "If multiple unrelated tokens share a similar name or ticker, ask the user for the exact token address. "
        "If the correct token is not found, re-run the tool using the provided address. "
        "Also advise the user to verify the token's legitimacy via its official social links included in the result."
    )
}


# Query Types
class QueryType(str, Enum):
    TEXT = "TEXT"
    TICKER = "TICKER"
    ADDRESS = "ADDRESS"


# Sort Options
class SortBy(str, Enum):
    LIQUIDITY = "liquidity"
    VOLUME = "volume"


# Volume Timeframes
class VolumeTimeframe(str, Enum):
    FIVE_MINUTES = "5_minutes"
    ONE_HOUR = "1_hour"
    SIX_HOUR = "6_hour"
    TWENTY_FOUR_HOUR = "24_hour"


# Supported Chain IDs
SUPPORTED_CHAINS = [
    "ethereum",
    "bsc",
    "polygon",
    "avalanche",
    "fantom",
    "cronos",
    "arbitrum",
    "optimism",
    "base",
    "solana",
    "sui",
    "tron",
    "ton",
]


def determine_query_type(query: str) -> QueryType:
    """
    Determine whether the query is a TEXT, TICKER, or ADDRESS.

    Args:
        query: The search query string

    Returns:
        QueryType enum value
    """
    if query.startswith("0x"):
        return QueryType.ADDRESS
    if query.startswith("$"):
        return QueryType.TICKER
    return QueryType.TEXT


def get_liquidity_value(pair: PairModel) -> float:
    """
    Extract liquidity USD value from a pair, defaulting to 0.0 if not available.

    Args:
        pair: PairModel instance

    Returns:
        Liquidity value in USD as float
    """
    return (
        pair.liquidity.usd if pair.liquidity and pair.liquidity.usd is not None else 0.0
    )


def get_volume_value(
    pair: PairModel, timeframe: VolumeTimeframe = VolumeTimeframe.TWENTY_FOUR_HOUR
) -> float:
    """
    Extract volume value from a pair for the specified timeframe.

    Args:
        pair: PairModel instance
        timeframe: VolumeTimeframe enum value

    Returns:
        Volume value as float
    """
    if not pair.volume:
        return 0.0

    volume_map = {
        VolumeTimeframe.FIVE_MINUTES: pair.volume.m5,
        VolumeTimeframe.ONE_HOUR: pair.volume.h1,
        VolumeTimeframe.SIX_HOUR: pair.volume.h6,
        VolumeTimeframe.TWENTY_FOUR_HOUR: pair.volume.h24,
    }

    return volume_map.get(timeframe, 0.0) or 0.0


def get_sort_function(
    sort_by: SortBy,
    volume_timeframe: VolumeTimeframe = VolumeTimeframe.TWENTY_FOUR_HOUR,
) -> Callable[[PairModel], float]:
    """
    Get the appropriate sorting function based on sort criteria.

    Args:
        sort_by: SortBy enum value
        volume_timeframe: VolumeTimeframe enum value (used when sorting by volume)

    Returns:
        Callable function that takes a PairModel and returns a float for sorting
    """
    if sort_by == SortBy.LIQUIDITY:
        return get_liquidity_value
    elif sort_by == SortBy.VOLUME:
        return lambda pair: get_volume_value(pair, volume_timeframe)
    else:
        logger.warning(f"Invalid sort_by value '{sort_by}', defaulting to liquidity.")
        return get_liquidity_value


def sort_pairs_by_criteria(
    pairs: List[PairModel],
    sort_by: SortBy = SortBy.LIQUIDITY,
    volume_timeframe: VolumeTimeframe = VolumeTimeframe.TWENTY_FOUR_HOUR,
    reverse: bool = True,
) -> List[PairModel]:
    """
    Sort pairs by the specified criteria.

    Args:
        pairs: List of PairModel instances to sort
        sort_by: Sorting criteria (liquidity or volume)
        volume_timeframe: Timeframe for volume sorting
        reverse: Sort in descending order if True

    Returns:
        Sorted list of PairModel instances
    """
    try:
        sort_func = get_sort_function(sort_by, volume_timeframe)
        return sorted(pairs, key=sort_func, reverse=reverse)
    except Exception as e:
        logger.error(f"Failed to sort pairs: {e}", exc_info=True)
        return pairs  # Return original list if sorting fails


def filter_ticker_pairs(pairs: List[PairModel], target_ticker: str) -> List[PairModel]:
    """
    Filter pairs to only include those where base token symbol matches target ticker.

    Args:
        pairs: List of PairModel instances
        target_ticker: Target ticker symbol (case-insensitive)

    Returns:
        Filtered list of PairModel instances
    """
    target_ticker_upper = target_ticker.upper()
    return [
        p
        for p in pairs
        if p.baseToken
        and p.baseToken.symbol
        and p.baseToken.symbol.upper() == target_ticker_upper
    ]


def filter_address_pairs(
    pairs: List[PairModel], target_address: str
) -> List[PairModel]:
    """
    Filter pairs to only include those matching the target address.
    Checks pairAddress, baseToken.address, and quoteToken.address.

    Args:
        pairs: List of PairModel instances
        target_address: Target address (case-insensitive)

    Returns:
        Filtered list of PairModel instances
    """
    target_address_lower = target_address.lower()
    return [
        p
        for p in pairs
        if (p.pairAddress and p.pairAddress.lower() == target_address_lower)
        or (
            p.baseToken
            and p.baseToken.address
            and p.baseToken.address.lower() == target_address_lower
        )
        or (
            p.quoteToken
            and p.quoteToken.address
            and p.quoteToken.address.lower() == target_address_lower
        )
    ]


def create_error_response(
    error_type: str,
    message: str,
    details: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a standardized error response in JSON format.

    Args:
        error_type: Type/category of error
        message: Human-readable error message
        details: Optional additional details about the error
        additional_data: Optional dictionary of additional data to include

    Returns:
        JSON string containing error information
    """
    response = {
        "error": message,
        "error_type": error_type,
    }

    if details:
        response["details"] = details

    if additional_data:
        response.update(additional_data)

    return json.dumps(response, indent=2)


def create_no_results_response(
    query_info: str,
    reason: str = "no results found",
    additional_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a standardized "no results found" response.

    Args:
        query_info: Information about the query that was performed
        reason: Reason why no results were found
        additional_data: Optional additional data to include

    Returns:
        JSON string containing no results information
    """
    response = {
        "message": f"No results found for the query. Reason: {reason}.",
        "query_info": query_info,
        "pairs": [],
    }

    if additional_data:
        response.update(additional_data)

    return json.dumps(response, indent=2)


def handle_validation_error(
    error: ValidationError, query_info: str, data_length: Optional[int] = None
) -> str:
    """
    Handle validation errors in a standardized way.

    Args:
        error: The ValidationError that occurred
        query_info: Information about the query being processed
        data_length: Optional length of the data that failed validation

    Returns:
        JSON error response string
    """
    log_message = f"Failed to validate DexScreener response structure for {query_info}. Error: {error}"
    if data_length:
        log_message += f". Raw data length: {data_length}"

    logger.error(log_message, exc_info=True)

    return create_error_response(
        error_type="validation_error",
        message="Failed to parse successful DexScreener API response",
        details=str(error.errors()),
        additional_data={"query_info": query_info},
    )


def truncate_large_fields(
    data: Dict[str, Any], max_length: int = 500
) -> Dict[str, Any]:
    """
    Truncate large string fields in error response data to avoid overwhelming the LLM.

    Args:
        data: Dictionary potentially containing large string fields
        max_length: Maximum length for string fields before truncation

    Returns:
        Dictionary with truncated fields
    """
    truncated = data.copy()

    for key in ["details", "response_body"]:
        if isinstance(truncated.get(key), str) and len(truncated[key]) > max_length:
            truncated[key] = truncated[key][:max_length] + "... (truncated)"

    return truncated


def group_pairs_by_token(pairs: List[PairModel]) -> Dict[str, List[PairModel]]:
    """
    Group pairs by token address for better organization in multi-token responses.

    Args:
        pairs: List of PairModel instances

    Returns:
        Dictionary mapping lowercase token addresses to lists of pairs
    """
    tokens_data = {}

    for pair in pairs:
        # Group by base token address
        if pair.baseToken and pair.baseToken.address:
            base_addr = pair.baseToken.address.lower()
            if base_addr not in tokens_data:
                tokens_data[base_addr] = []
            tokens_data[base_addr].append(pair)

        # Group by quote token address
        if pair.quoteToken and pair.quoteToken.address:
            quote_addr = pair.quoteToken.address.lower()
            if quote_addr not in tokens_data:
                tokens_data[quote_addr] = []
            tokens_data[quote_addr].append(pair)

    return tokens_data


def validate_chain_id(chain_id: str) -> bool:
    """
    Validate if the chain ID is supported.

    Args:
        chain_id: Chain ID to validate

    Returns:
        True if chain ID is supported, False otherwise
    """
    return chain_id.lower() in SUPPORTED_CHAINS


def format_success_response(data: Dict[str, Any]) -> str:
    """
    Format a successful response as JSON string.

    Args:
        data: Response data dictionary

    Returns:
        JSON formatted string
    """
    return json.dumps(data, indent=2)
