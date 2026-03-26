"""Aave V3 lending protocol skills."""

import logging
from typing import Any, TypedDict

from intentkit.skills.aave_v3.base import AaveV3BaseTool
from intentkit.skills.aave_v3.borrow import AaveV3Borrow
from intentkit.skills.aave_v3.get_reserve_data import AaveV3GetReserveData
from intentkit.skills.aave_v3.get_user_account_data import AaveV3GetUserAccountData
from intentkit.skills.aave_v3.repay import AaveV3Repay
from intentkit.skills.aave_v3.set_collateral import AaveV3SetCollateral
from intentkit.skills.aave_v3.supply import AaveV3Supply
from intentkit.skills.aave_v3.withdraw import AaveV3Withdraw
from intentkit.skills.base import SkillConfig, SkillState

logger = logging.getLogger(__name__)

_cache: dict[str, AaveV3BaseTool] = {}


class SkillStates(TypedDict):
    aave_v3_get_user_account_data: SkillState
    aave_v3_get_reserve_data: SkillState
    aave_v3_supply: SkillState
    aave_v3_withdraw: SkillState
    aave_v3_borrow: SkillState
    aave_v3_repay: SkillState
    aave_v3_set_collateral: SkillState


class Config(SkillConfig):
    """Configuration for Aave V3 skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_: Any,
) -> list[AaveV3BaseTool]:
    """Get all Aave V3 skills."""
    available_skills: list[str] = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    result: list[AaveV3BaseTool] = []
    for name in available_skills:
        skill = _get_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_skill(name: str) -> AaveV3BaseTool | None:
    if name not in _cache:
        if name == "aave_v3_get_user_account_data":
            _cache[name] = AaveV3GetUserAccountData()
        elif name == "aave_v3_get_reserve_data":
            _cache[name] = AaveV3GetReserveData()
        elif name == "aave_v3_supply":
            _cache[name] = AaveV3Supply()
        elif name == "aave_v3_withdraw":
            _cache[name] = AaveV3Withdraw()
        elif name == "aave_v3_borrow":
            _cache[name] = AaveV3Borrow()
        elif name == "aave_v3_repay":
            _cache[name] = AaveV3Repay()
        elif name == "aave_v3_set_collateral":
            _cache[name] = AaveV3SetCollateral()
        else:
            logger.warning("Unknown aave_v3 skill: %s", name)
            return None
    return _cache[name]


def available() -> bool:
    """Aave V3 requires no platform API keys."""
    return True
