"""OpenSea NFT marketplace tools."""

from intentkit.config.config import config as system_config
from intentkit.tools.base import IntentKitTool
from intentkit.tools.opensea.buy_nft import OpenSeaBuyNft
from intentkit.tools.opensea.cancel_listing import OpenSeaCancelListing
from intentkit.tools.opensea.create_listing import OpenSeaCreateListing
from intentkit.tools.opensea.get_collection import OpenSeaGetCollection
from intentkit.tools.opensea.get_collection_stats import OpenSeaGetCollectionStats
from intentkit.tools.opensea.get_events import OpenSeaGetEvents
from intentkit.tools.opensea.get_listings import OpenSeaGetListings
from intentkit.tools.opensea.get_nft import OpenSeaGetNft
from intentkit.tools.opensea.get_nfts_by_account import OpenSeaGetNftsByAccount
from intentkit.tools.opensea.get_offers import OpenSeaGetOffers
from intentkit.tools.opensea.update_listing import OpenSeaUpdateListing

# Cache tools at the system level, because they are stateless
_cache: dict[str, IntentKitTool] = {}

_TOOL_NAME_TO_CLASS_MAP: dict[str, type[IntentKitTool]] = {
    "opensea_get_collection": OpenSeaGetCollection,
    "opensea_get_collection_stats": OpenSeaGetCollectionStats,
    "opensea_get_nft": OpenSeaGetNft,
    "opensea_get_listings": OpenSeaGetListings,
    "opensea_get_offers": OpenSeaGetOffers,
    "opensea_get_events": OpenSeaGetEvents,
    "opensea_get_nfts_by_account": OpenSeaGetNftsByAccount,
    "opensea_create_listing": OpenSeaCreateListing,
    "opensea_buy_nft": OpenSeaBuyNft,
    "opensea_cancel_listing": OpenSeaCancelListing,
    "opensea_update_listing": OpenSeaUpdateListing,
}


async def get_tools(tool_names: list[str], **_) -> list[IntentKitTool]:
    """Get the requested OpenSea tools; unknown names are skipped."""
    return [tool for name in tool_names if (tool := get_opensea_tool(name))]


def get_opensea_tool(tool_name: str) -> IntentKitTool | None:
    """Get an OpenSea tool by name, using the instance cache."""
    if tool_name in _cache:
        return _cache[tool_name]

    tool_class = _TOOL_NAME_TO_CLASS_MAP.get(tool_name)
    if not tool_class:
        return None

    _cache[tool_name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[tool_name]


def available() -> bool:
    """Check if OpenSea tools are available (API key configured)."""
    return bool(system_config.opensea_api_key)
