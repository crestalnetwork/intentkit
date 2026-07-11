"""Morpho lending protocol tools."""

from intentkit.tools.meta import ToolsetMeta
from intentkit.tools.morpho.base import MorphoBaseTool
from intentkit.tools.morpho.borrow import MorphoBorrow
from intentkit.tools.morpho.deposit import MorphoDeposit
from intentkit.tools.morpho.get_position import MorphoGetPosition
from intentkit.tools.morpho.get_vault_data import MorphoGetVaultData
from intentkit.tools.morpho.repay import MorphoRepay
from intentkit.tools.morpho.supply_collateral import MorphoSupplyCollateral
from intentkit.tools.morpho.withdraw import MorphoWithdraw
from intentkit.tools.morpho.withdraw_collateral import MorphoWithdrawCollateral

toolset = ToolsetMeta(
    title="Morpho",
    description="Morpho protocol actions for vaults (deposit/withdraw) and Morpho Blue markets (collateral, borrow, repay)",
    tags=["DeFi"],
    wallet=True,
    icon="/tools/morpho/morpho.svg",
)


# Cache for tool instances
_cache: dict[str, MorphoBaseTool] = {
    "morpho_deposit": MorphoDeposit(),
    "morpho_withdraw": MorphoWithdraw(),
    "morpho_get_vault_data": MorphoGetVaultData(),
    "morpho_supply_collateral": MorphoSupplyCollateral(),
    "morpho_withdraw_collateral": MorphoWithdrawCollateral(),
    "morpho_borrow": MorphoBorrow(),
    "morpho_repay": MorphoRepay(),
    "morpho_get_position": MorphoGetPosition(),
}


async def get_tools(tool_names: list[str], **_) -> list[MorphoBaseTool]:
    """Get the requested Morpho tools; unknown names are skipped."""
    return [_cache[name] for name in tool_names if name in _cache]


def available() -> bool:
    """Check if this toolset is available based on system config.

    Morpho tools are available for any EVM-compatible wallet (CDP, Safe/Privy)
    on supported networks (base-mainnet, base-sepolia).
    """
    return True
