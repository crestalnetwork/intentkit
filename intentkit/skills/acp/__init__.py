"""ACP (Agentic Commerce Protocol) skill category."""

import logging
from typing import TypedDict

from intentkit.skills.base import SkillConfig, SkillState

from .base import AcpBaseTool
from .cancel_checkout import AcpCancelCheckout
from .complete_checkout import AcpCompleteCheckout
from .create_checkout import AcpCreateCheckout
from .get_checkout import AcpGetCheckout
from .list_products import AcpListProducts

logger = logging.getLogger(__name__)

_cache: dict[str, AcpBaseTool] = {}


class SkillStates(TypedDict):
    acp_list_products: SkillState
    acp_create_checkout: SkillState
    acp_get_checkout: SkillState
    acp_complete_checkout: SkillState
    acp_cancel_checkout: SkillState


class Config(SkillConfig):
    """Configuration for ACP skills."""

    states: SkillStates


_SKILL_BUILDERS: dict[str, type[AcpBaseTool]] = {
    "acp_list_products": AcpListProducts,
    "acp_create_checkout": AcpCreateCheckout,
    "acp_get_checkout": AcpGetCheckout,
    "acp_complete_checkout": AcpCompleteCheckout,
    "acp_cancel_checkout": AcpCancelCheckout,
}


async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[AcpBaseTool]:
    """Return enabled ACP skills for the agent."""
    enabled_skills = []
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        if state == "public" or (state == "private" and is_private):
            enabled_skills.append(skill_name)

    result: list[AcpBaseTool] = []
    for name in enabled_skills:
        skill = _get_skill(name)
        if skill:
            result.append(skill)
    return result


def _get_skill(name: str) -> AcpBaseTool | None:
    builder = _SKILL_BUILDERS.get(name)
    if builder:
        if name not in _cache:
            _cache[name] = builder()
        return _cache[name]
    logger.warning("Unknown ACP skill requested: %s", name)
    return None


def available() -> bool:
    """Check if this skill category is available."""
    return True
