"""Basename tools for ENS-style domain registration on Base."""

from typing import Any

from intentkit.config.config import config as system_config
from intentkit.tools.basename.base import BasenameBaseTool
from intentkit.tools.basename.register import BasenameRegister
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="Basename",
    description="Basename ENS-style name registration on Base network",
    tags=["Crypto", "Identity"],
    wallet=True,
    icon="/tools/basename/basename.svg",
)


# Cache for tool instances
_cache: dict[str, BasenameBaseTool] = {
    "basename_register_basename": BasenameRegister(),
}


async def get_tools(tool_names: list[str], **_: Any) -> list[BasenameBaseTool]:
    """Return Basename tool instances for the requested names."""
    return [_cache[name] for name in tool_names if name in _cache]


def available() -> bool:
    """Check if this toolset is available based on system config.

    Basename tools require CDP credentials for wallet operations,
    or can work with Safe/Privy wallet providers.
    """
    # Basename works with any on-chain capable wallet
    # Check if we have at least CDP credentials configured
    has_cdp = all(
        [
            bool(system_config.cdp_api_key_id),
            bool(system_config.cdp_api_key_secret),
            bool(system_config.cdp_wallet_secret),
        ]
    )
    # Or Privy credentials
    has_privy = bool(system_config.privy_app_id) and bool(
        system_config.privy_app_secret
    )

    return has_cdp or has_privy
