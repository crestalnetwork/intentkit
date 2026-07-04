"""CDP wallet interaction tools.

This module provides wallet tools that require a CDP wallet provider.
"""

from typing import Any

from intentkit.tools.cdp.base import CDPBaseTool
from intentkit.tools.cdp.get_balance import CDPGetBalance
from intentkit.tools.cdp.get_wallet_details import CDPGetWalletDetails
from intentkit.tools.cdp.native_transfer import CDPNativeTransfer

# Cache for tool instances
_cache: dict[str, CDPBaseTool] = {
    "cdp_get_balance": CDPGetBalance(),
    "cdp_get_wallet_details": CDPGetWalletDetails(),
    "cdp_native_transfer": CDPNativeTransfer(),
}


async def get_tools(tool_names: list[str], **_: Any) -> list[CDPBaseTool]:
    """Return CDP tool instances for the requested names."""
    return [_cache[name] for name in tool_names if name in _cache]


def available() -> bool:
    """Check if this toolset is available based on system config.

    CDP wallet tools are globally available but require the agent's
    wallet provider to be configured as 'cdp'.
    """
    return True
