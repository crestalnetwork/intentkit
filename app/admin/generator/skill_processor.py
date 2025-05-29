"""Skill Processing Module.

This module handles all skill-related operations for agent generation including:
- Skill identification from prompts
- Skill validation and filtering
- Keyword and AI-based skill matching
"""

import importlib
import logging
from typing import Any, Dict, Set

from openai import OpenAI

from skills import __all__ as available_skill_categories

logger = logging.getLogger(__name__)

# Get available skill categories from the skills module
AVAILABLE_SKILL_CATEGORIES = set(available_skill_categories)

# Cache for skill states to avoid repeated imports
_skill_states_cache: Dict[str, Set[str]] = {}
_all_skills_cache: Dict[str, Dict[str, Set[str]]] = {}


def get_skill_states(skill_category: str) -> Set[str]:
    """Get the actual skill states for a given skill category by importing its module."""
    if skill_category in _skill_states_cache:
        return _skill_states_cache[skill_category]

    try:
        # Import the skill category module
        skill_module = importlib.import_module(f"skills.{skill_category}")

        # Look for the SkillStates TypedDict class
        if hasattr(skill_module, "SkillStates"):
            skill_states_class = getattr(skill_module, "SkillStates")
            # Get the annotations which contain the state names
            if hasattr(skill_states_class, "__annotations__"):
                states = set(skill_states_class.__annotations__.keys())
                _skill_states_cache[skill_category] = states
                return states

        logger.warning(f"Could not find SkillStates for {skill_category}")
        return set()

    except ImportError as e:
        logger.warning(f"Could not import skill category {skill_category}: {e}")
        return set()


def get_all_real_skills() -> Dict[str, Set[str]]:
    """Get ALL real skills and their states from the codebase."""
    if _all_skills_cache:
        return _all_skills_cache

    all_skills = {}
    for skill_category in AVAILABLE_SKILL_CATEGORIES:
        states = get_skill_states(skill_category)
        if states:
            all_skills[skill_category] = states

    _all_skills_cache.update(all_skills)
    return all_skills


# Keyword to skill mapping configuration
SKILL_KEYWORD_CONFIG = {
    # Web & Research
    "tavily": ["search", "web", "research", "extract", "tavily"],
    # Social Media
    "twitter": ["twitter", "tweet", "social"],
    "slack": ["slack", "messaging"],
    # Crypto & DeFi
    "cryptocompare": ["crypto", "price", "cryptocompare"],
    "token": ["token", "balance"],
    "defillama": ["defi", "tvl", "defillama"],
    "dexscreener": ["dex", "dexscreener"],
    "dune_analytics": ["dune", "analytics", "dune_analytics"],
    # Blockchain
    "cdp": ["wallet", "blockchain", "cdp"],
    "portfolio": ["portfolio"],
    "moralis": ["moralis", "web3"],
    # Development
    "github": ["github", "git"],
    # Media Generation
    "venice_image": ["image", "venice_image"],
    "unrealspeech": ["speech", "unrealspeech"],
    "openai": ["vision", "openai"],
    # Utilities
    "common": ["time", "weather", "random", "common"],
}


def get_skill_mapping() -> Dict[str, Dict[str, Set[str]]]:
    """Generate skill mapping dynamically from actual skill implementations."""
    mapping = {}
    all_real_skills = get_all_real_skills()

    # Build mapping from configuration
    for skill_name, keywords in SKILL_KEYWORD_CONFIG.items():
        if skill_name in all_real_skills:
            skill_states = all_real_skills[skill_name]

            # Special case for twitter tweet - use only post_tweet state
            if skill_name == "twitter":
                for keyword in keywords:
                    if keyword == "tweet":
                        mapping[keyword] = {
                            skill_name: {"post_tweet"}
                            if "post_tweet" in skill_states
                            else skill_states
                        }
                    else:
                        mapping[keyword] = {skill_name: skill_states}
            else:
                # Standard mapping for all keywords
                for keyword in keywords:
                    mapping[keyword] = {skill_name: skill_states}

    # Add direct skill name mappings for any skills not in config
    for skill_name, skill_states in all_real_skills.items():
        if skill_name not in SKILL_KEYWORD_CONFIG and skill_name not in mapping:
            mapping[skill_name] = {skill_name: skill_states}

    return mapping


def add_skill_by_name(prompt: str, skills_config: Dict[str, Any]) -> Dict[str, Any]:
    """Add skills mentioned by exact name in the prompt."""
    all_real_skills = get_all_real_skills()
    prompt_lower = prompt.lower()

    # Check for exact skill name matches
    for skill_name in all_real_skills.keys():
        if skill_name in prompt_lower:
            states = all_real_skills[skill_name]
            skills_config[skill_name] = {
                "enabled": True,
                "states": {state: "public" for state in states},
                "api_key_provider": "platform",
            }

    # Handle "add all X skills" pattern
    if "add all" in prompt_lower:
        for skill_name in all_real_skills.keys():
            if f"all {skill_name}" in prompt_lower:
                states = all_real_skills[skill_name]
                skills_config[skill_name] = {
                    "enabled": True,
                    "states": {state: "public" for state in states},
                    "api_key_provider": "platform",
                }

    return skills_config


# Skills that require agent owner to provide API keys (should be excluded from auto-generation)
AGENT_OWNER_API_KEY_SKILLS = {
    "dune_analytics",
    "dapplooker",
    "cryptocompare",
    "aixbt",
}

# Skills that have configurable API key providers but default to platform
CONFIGURABLE_API_KEY_SKILLS = {
    "tavily",
    "twitter",
    "slack",
    "telegram",
    "moralis",
    "token",
    "portfolio",
    "openai",
    "heurist",
    "cookiefun",
    "enso",
}


async def validate_skills_exist(skills_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that all skills in the config actually exist in IntentKit.

    Args:
        skills_config: Skills configuration to validate

    Returns:
        Validated skills configuration with only existing skills
    """
    validated_skills = {}

    for skill_name, skill_config in skills_config.items():
        if skill_name in AVAILABLE_SKILL_CATEGORIES:
            validated_skills[skill_name] = skill_config
        else:
            logger.warning(
                f"Skipping non-existent skill '{skill_name}' - only available skills: {list(AVAILABLE_SKILL_CATEGORIES)}"
            )

    return validated_skills


async def filter_skills_for_auto_generation(
    skills_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Filter out skills that require agent owner API keys from auto-generation.

    Args:
        skills_config: Original skills configuration

    Returns:
        Filtered skills configuration without agent-owner API key requirements
    """
    # First validate that all skills exist
    skills_config = await validate_skills_exist(skills_config)

    filtered_skills = {}

    for skill_name, skill_config in skills_config.items():
        # Skip skills that always require agent owner API keys
        if skill_name in AGENT_OWNER_API_KEY_SKILLS:
            logger.info(
                f"Excluding skill '{skill_name}' from auto-generation: requires agent owner API key"
            )
            continue

        # For configurable skills, ensure we set api_key_provider to platform
        if skill_name in CONFIGURABLE_API_KEY_SKILLS:
            skill_config = skill_config.copy()
            skill_config["api_key_provider"] = "platform"

        filtered_skills[skill_name] = skill_config

    return filtered_skills


async def identify_skills(prompt: str, client: OpenAI) -> Dict[str, Any]:
    """Identify relevant skills from the prompt using only real skill data.

    Args:
        prompt: The natural language prompt
        client: OpenAI client (not used, kept for compatibility)

    Returns:
        Dict containing skill configurations with only real skill states
    """
    # Use keyword matching first
    skills_config = keyword_match_skills(prompt)

    # Add skills mentioned by exact name
    skills_config = add_skill_by_name(prompt, skills_config)
    return skills_config


def keyword_match_skills(prompt: str) -> Dict[str, Any]:
    """Match skills using keyword matching with real skill states only.

    Args:
        prompt: The natural language prompt

    Returns:
        Dict containing skill configurations with real states only
    """
    skills_config = {}
    prompt_lower = prompt.lower()

    for keyword, skill_mapping in get_skill_mapping().items():
        if keyword.lower() in prompt_lower:
            for skill_name, states in skill_mapping.items():
                if skill_name not in skills_config:
                    skills_config[skill_name] = {
                        "enabled": True,
                        "states": {state: "public" for state in states},
                        "api_key_provider": "platform",
                    }
                else:
                    # Merge states if skill already exists
                    existing_states = skills_config[skill_name]["states"]
                    for state in states:
                        existing_states[state] = "public"

    return skills_config
