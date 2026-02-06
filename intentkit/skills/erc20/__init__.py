"""ERC20 token skills."""

from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.erc20.base import ERC20BaseTool
from intentkit.skills.erc20.get_balance import ERC20GetBalance
from intentkit.skills.erc20.get_token_address import ERC20GetTokenAddress
from intentkit.skills.erc20.transfer import ERC20Transfer


class SkillStates(TypedDict):
    erc20_get_balance: SkillState
    erc20_transfer: SkillState
    erc20_get_token_address: SkillState


class Config(SkillConfig):
    """Configuration for ERC20 skills."""

    states: SkillStates


# Cache for skill instances
_cache: dict[str, ERC20BaseTool] = {
    "erc20_get_balance": ERC20GetBalance(),
    "erc20_transfer": ERC20Transfer(),
    "erc20_get_token_address": ERC20GetTokenAddress(),
}


async def get_skills(
    config: Config,
    is_private: bool,
    **_,
) -> list[ERC20BaseTool]:
    """Get all enabled ERC20 skills.

    Args:
        config: The configuration for ERC20 skills.
        is_private: Whether to include private skills.

    Returns:
        A list of enabled ERC20 skills.
    """
    tools: list[ERC20BaseTool] = []

    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            # Check cache first
            if skill_name in _cache:
                tools.append(_cache[skill_name])

    return tools


def available() -> bool:
    """Check if this skill category is available based on system config.

    ERC20 skills are available for any EVM-compatible wallet (CDP, Safe/Privy).
    They don't require specific CDP credentials since they work with any wallet.
    """
    return True
