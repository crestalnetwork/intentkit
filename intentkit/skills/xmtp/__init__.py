"""XMTP skills."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.xmtp.base import XmtpBaseTool
from intentkit.skills.xmtp.price import XmtpGetSwapPrice
from intentkit.skills.xmtp.swap import XmtpSwap
from intentkit.skills.xmtp.transfer import XmtpTransfer

# Cache skills at the module level, because they are stateless
_cache: dict[str, XmtpBaseTool] = {}

logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    xmtp_transfer: SkillState
    xmtp_swap: SkillState
    xmtp_get_swap_price: SkillState


class Config(SkillConfig):
    """Configuration for XMTP skills."""

    states: SkillStates


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[XmtpBaseTool]:
    """Get all XMTP skills.

    Args:
        config: The configuration for XMTP skills.
        is_private: Whether to include private skills.

    Returns:
        A list of XMTP skills.
    """
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    result = []
    for name in available_skills:
        skill = get_xmtp_skill(name)
        if skill:
            result.append(skill)
    return result


def get_xmtp_skill(
    name: str,
) -> XmtpBaseTool:
    """Get an XMTP skill by name.

    Args:
        name: The name of the skill to get

    Returns:
        The requested XMTP skill
    """
    if name == "xmtp_transfer":
        if name not in _cache:
            _cache[name] = XmtpTransfer()
        return _cache[name]
    elif name == "xmtp_swap":
        if name not in _cache:
            _cache[name] = XmtpSwap()
        return _cache[name]
    elif name == "xmtp_get_swap_price":
        if name not in _cache:
            _cache[name] = XmtpGetSwapPrice()
        return _cache[name]
    else:
        logger.warning(f"Unknown XMTP skill: {name}")
        return None
