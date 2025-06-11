import logging
from typing import List, Optional, TypedDict

from abstracts.skill import SkillStoreABC
from skills.base import SkillConfig, SkillState
from skills.lifi.base import LiFiBaseTool
from skills.lifi.token_execute import TokenExecute
from skills.lifi.token_quote import TokenQuote

# Cache skills at the system level, because they are stateless
_cache: dict[str, LiFiBaseTool] = {}

# Set up logging
logger = logging.getLogger(__name__)


class SkillStates(TypedDict):
    token_quote: SkillState
    token_execute: SkillState


class Config(SkillConfig):
    """Configuration for LiFi skills."""

    states: SkillStates
    default_slippage: Optional[float] = 0.03
    allowed_chains: Optional[List[str]] = None
    max_execution_time: Optional[int] = 300


async def get_skills(
    config: "Config",
    is_private: bool,
    store: SkillStoreABC,
    **_,
) -> list[LiFiBaseTool]:
    """Get all LiFi skills."""
    available_skills = []

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)

    # Get each skill using the cached getter
    return [get_lifi_skill(name, store, config) for name in available_skills]


def get_lifi_skill(
    name: str,
    store: SkillStoreABC,
    config: Config,
) -> LiFiBaseTool:
    """Get a LiFi skill by name."""
    # Create a cache key that includes configuration to ensure skills
    # with different configurations are treated as separate instances
    cache_key = f"{name}_{id(config)}"

    # Extract configuration options
    default_slippage = config.get("default_slippage", 0.03)
    allowed_chains = config.get("allowed_chains", None)
    max_execution_time = config.get("max_execution_time", 300)

    if name == "token_quote":
        if cache_key not in _cache:
            logger.info("[LiFi_Skill] Initializing token_quote skill")

            _cache[cache_key] = TokenQuote(
                skill_store=store,
                default_slippage=default_slippage,
                allowed_chains=allowed_chains,
            )
        return _cache[cache_key]
    elif name == "token_execute":
        if cache_key not in _cache:
            # Log a warning about CDP wallet requirements
            logger.info(
                "[LiFi_Skill] Initializing token_execute skill - Note: CDP wallet is required"
            )

            _cache[cache_key] = TokenExecute(
                skill_store=store,
                default_slippage=default_slippage,
                allowed_chains=allowed_chains,
                max_execution_time=max_execution_time,
            )
        return _cache[cache_key]
    else:
        raise ValueError(f"Unknown LiFi skill: {name}")
