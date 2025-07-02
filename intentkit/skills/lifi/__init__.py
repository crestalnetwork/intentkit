import logging
from typing import List, Optional, TypedDict

from intentkit.abstracts.skill import SkillStoreABC
from intentkit.skills.base import SkillConfig, SkillState
from intentkit.skills.lifi.base import LiFiBaseTool
from intentkit.skills.lifi.token_execute import TokenExecute
from intentkit.skills.lifi.token_quote import TokenQuote

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

    # Log configuration
    logger.info(f"[LiFi_Skills] Initializing with config: {config}")
    logger.info(f"[LiFi_Skills] Is private session: {is_private}")

    # Include skills based on their state
    for skill_name, state in config["states"].items():
        if state == "disabled":
            logger.info(f"[LiFi_Skills] Skipping disabled skill: {skill_name}")
            continue
        elif state == "public" or (state == "private" and is_private):
            available_skills.append(skill_name)
            logger.info(f"[LiFi_Skills] Including skill: {skill_name} (state: {state})")
        else:
            logger.info(
                f"[LiFi_Skills] Skipping private skill in public session: {skill_name}"
            )

    logger.info(f"[LiFi_Skills] Available skills: {available_skills}")

    # Get each skill using the cached getter
    skills = []
    for name in available_skills:
        try:
            skill = get_lifi_skill(name, store, config)
            skills.append(skill)
            logger.info(f"[LiFi_Skills] Successfully loaded skill: {name}")
        except Exception as e:
            logger.error(f"[LiFi_Skills] Failed to load skill {name}: {str(e)}")
            # Continue loading other skills even if one fails

    logger.info(f"[LiFi_Skills] Total skills loaded: {len(skills)}")
    return skills


def get_lifi_skill(
    name: str,
    store: SkillStoreABC,
    config: Config,
) -> LiFiBaseTool:
    """Get a LiFi skill by name."""
    # Create a cache key that includes configuration to ensure skills
    # with different configurations are treated as separate instances
    cache_key = f"{name}_{id(config)}"

    # Extract configuration options with proper defaults
    default_slippage = config.get("default_slippage", 0.03)
    allowed_chains = config.get("allowed_chains", None)
    max_execution_time = config.get("max_execution_time", 300)

    # Validate configuration
    if default_slippage < 0.001 or default_slippage > 0.5:
        logger.warning(
            f"[LiFi_Skills] Invalid default_slippage: {default_slippage}, using 0.03"
        )
        default_slippage = 0.03

    if max_execution_time < 60 or max_execution_time > 1800:
        logger.warning(
            f"[LiFi_Skills] Invalid max_execution_time: {max_execution_time}, using 300"
        )
        max_execution_time = 300

    if name == "token_quote":
        if cache_key not in _cache:
            logger.info(
                f"[LiFi_Skills] Initializing token_quote skill with slippage: {default_slippage}"
            )
            if allowed_chains:
                logger.info(f"[LiFi_Skills] Allowed chains: {allowed_chains}")

            _cache[cache_key] = TokenQuote(
                skill_store=store,
                default_slippage=default_slippage,
                allowed_chains=allowed_chains,
            )
        return _cache[cache_key]

    elif name == "token_execute":
        if cache_key not in _cache:
            logger.info("[LiFi_Skills] Initializing token_execute skill")
            logger.info(
                f"[LiFi_Skills] Configuration - slippage: {default_slippage}, max_time: {max_execution_time}"
            )
            if allowed_chains:
                logger.info(f"[LiFi_Skills] Allowed chains: {allowed_chains}")

            # Log a warning about CDP wallet requirements
            logger.warning(
                "[LiFi_Skills] token_execute requires a properly configured CDP wallet with sufficient funds"
            )

            _cache[cache_key] = TokenExecute(
                skill_store=store,
                default_slippage=default_slippage,
                allowed_chains=allowed_chains,
                max_execution_time=max_execution_time,
            )
        return _cache[cache_key]

    else:
        logger.error(f"[LiFi_Skills] Unknown LiFi skill requested: {name}")
        raise ValueError(f"Unknown LiFi skill: {name}")
