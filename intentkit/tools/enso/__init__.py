"""Enso tools."""

import logging
from collections.abc import Callable

from intentkit.config.config import config as system_config
from intentkit.tools.enso.base import EnsoBaseTool
from intentkit.tools.enso.best_yield import EnsoGetBestYield
from intentkit.tools.enso.networks import EnsoGetNetworks
from intentkit.tools.enso.prices import EnsoGetPrices
from intentkit.tools.enso.route import EnsoRouteShortcut
from intentkit.tools.enso.tokens import EnsoGetTokens
from intentkit.tools.enso.wallet import (
    EnsoGetWalletApprovals,
    EnsoGetWalletBalances,
    EnsoWalletApprove,
)

logger = logging.getLogger(__name__)

_TOOL_CLASSES: dict[str, Callable[[], EnsoBaseTool]] = {
    "enso_get_networks": EnsoGetNetworks,
    "enso_get_tokens": EnsoGetTokens,
    "enso_get_prices": EnsoGetPrices,
    "enso_get_wallet_approvals": EnsoGetWalletApprovals,
    "enso_get_wallet_balances": EnsoGetWalletBalances,
    "enso_wallet_approve": EnsoWalletApprove,
    "enso_route_shortcut": EnsoRouteShortcut,
    "enso_get_best_yield": EnsoGetBestYield,
}


async def get_tools(tool_names: list[str], **_) -> list[EnsoBaseTool]:
    """Get the requested Enso tools."""
    return [tool for name in tool_names if (tool := get_enso_tool(name))]


def get_enso_tool(tool_name: str) -> EnsoBaseTool | None:
    """Get an Enso tool by name."""
    tool_class = _TOOL_CLASSES.get(tool_name)
    if tool_class is None:
        logger.warning("Unknown Enso tool: %s", tool_name)
        return None
    return tool_class()


def available() -> bool:
    """Check if this toolset is available based on system config."""
    return bool(system_config.enso_api_token)
