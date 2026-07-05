"""Aave V3 lending protocol tools."""

from typing import Any

from intentkit.tools.aave_v3.base import AaveV3BaseTool
from intentkit.tools.aave_v3.borrow import AaveV3Borrow
from intentkit.tools.aave_v3.get_reserve_data import AaveV3GetReserveData
from intentkit.tools.aave_v3.get_user_account_data import AaveV3GetUserAccountData
from intentkit.tools.aave_v3.repay import AaveV3Repay
from intentkit.tools.aave_v3.set_collateral import AaveV3SetCollateral
from intentkit.tools.aave_v3.supply import AaveV3Supply
from intentkit.tools.aave_v3.withdraw import AaveV3Withdraw
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="Aave V3",
    description="Aave V3 lending protocol: supply, borrow, repay, and manage collateral positions across multiple EVM chains",
    tags=["DeFi"],
    web3=True,
    icon="/tools/aave_v3/aave_v3.svg",
)


_cache: dict[str, AaveV3BaseTool] = {}

_TOOL_CLASSES: dict[str, type[AaveV3BaseTool]] = {
    "aave_v3_get_user_account_data": AaveV3GetUserAccountData,
    "aave_v3_get_reserve_data": AaveV3GetReserveData,
    "aave_v3_supply": AaveV3Supply,
    "aave_v3_withdraw": AaveV3Withdraw,
    "aave_v3_borrow": AaveV3Borrow,
    "aave_v3_repay": AaveV3Repay,
    "aave_v3_set_collateral": AaveV3SetCollateral,
}


async def get_tools(tool_names: list[str], **_: Any) -> list[AaveV3BaseTool]:
    """Return Aave V3 tool instances for the requested names."""
    result: list[AaveV3BaseTool] = []
    for name in tool_names:
        tool = _get_tool(name)
        if tool:
            result.append(tool)
    return result


def _get_tool(name: str) -> AaveV3BaseTool | None:
    tool_class = _TOOL_CLASSES.get(name)
    if tool_class is None:
        return None
    if name not in _cache:
        _cache[name] = tool_class()  # pyright: ignore[reportCallIssue]
    return _cache[name]


def available() -> bool:
    """Aave V3 requires no platform API keys."""
    return True
