"""Skill Processing Module.

This module handles all skill-related operations for agent generation including:
- Skill identification from prompts
- Skill validation and filtering
- Keyword and AI-based skill matching
"""

import importlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from openai import OpenAI

from skills import __all__ as available_skill_categories

if TYPE_CHECKING:
    from .llm_logger import LLMLogger

logger = logging.getLogger(__name__)

# Get available skill categories from the skills module
AVAILABLE_SKILL_CATEGORIES = set(available_skill_categories)

# Cache for skill states to avoid repeated imports
_skill_states_cache: Dict[str, Set[str]] = {}
_all_skills_cache: Dict[str, Dict[str, Set[str]]] = {}
_skill_schemas_cache: Dict[str, Dict[str, Any]] = {}


def load_skill_schema(skill_name: str) -> Optional[Dict[str, Any]]:
    """Load schema.json for a specific skill."""
    if skill_name in _skill_schemas_cache:
        return _skill_schemas_cache[skill_name]

    try:
        # Get the skills directory path
        skills_dir = Path(__file__).parent.parent.parent.parent / "skills"
        schema_path = skills_dir / skill_name / "schema.json"

        if schema_path.exists():
            with open(schema_path, "r") as f:
                schema = json.load(f)
                _skill_schemas_cache[skill_name] = schema
                return schema
        else:
            logger.warning(f"Schema file not found for skill: {skill_name}")
            return None
    except Exception as e:
        logger.error(f"Error loading schema for skill {skill_name}: {e}")
        return None


def get_agent_owner_api_key_skills() -> Set[str]:
    """Get skills that require agent owner API keys."""
    agent_owner_skills = set()

    for skill_name in AVAILABLE_SKILL_CATEGORIES:
        try:
            schema = load_skill_schema(skill_name)
            if (
                schema
                and "properties" in schema
                and "api_key_provider" in schema["properties"]
            ):
                api_key_provider = schema["properties"]["api_key_provider"]
                if "enum" in api_key_provider and api_key_provider["enum"] == [
                    "agent_owner"
                ]:
                    agent_owner_skills.add(skill_name)
        except Exception as e:
            logger.warning(
                f"Error checking API key requirement for skill {skill_name}: {e}"
            )

    return agent_owner_skills


def get_configurable_api_key_skills() -> Set[str]:
    """Get skills with configurable API key providers."""
    configurable_skills = set()

    for skill_name in AVAILABLE_SKILL_CATEGORIES:
        try:
            schema = load_skill_schema(skill_name)
            if (
                schema
                and "properties" in schema
                and "api_key_provider" in schema["properties"]
            ):
                api_key_provider = schema["properties"]["api_key_provider"]
                if "enum" in api_key_provider:
                    enum_values = set(api_key_provider["enum"])
                    if "platform" in enum_values and "agent_owner" in enum_values:
                        configurable_skills.add(skill_name)
        except Exception as e:
            logger.warning(
                f"Error checking API key configurability for skill {skill_name}: {e}"
            )

    return configurable_skills


def get_skill_keyword_config() -> Dict[str, List[str]]:
    """Generate skill keyword configuration from schemas."""
    config = {}

    for skill_name in AVAILABLE_SKILL_CATEGORIES:
        try:
            schema = load_skill_schema(skill_name)
            keywords = [skill_name]  # Always include skill name

            if schema:
                # Add title words
                if "title" in schema:
                    keywords.extend(schema["title"].lower().split())

                # Add x-tags
                if "x-tags" in schema:
                    keywords.extend([tag.lower() for tag in schema["x-tags"]])

            config[skill_name] = keywords
        except Exception as e:
            logger.warning(f"Error getting keywords for skill {skill_name}: {e}")
            config[skill_name] = [skill_name]

    return config


def get_skill_state_default(skill_name: str, state_name: str) -> str:
    """Get the default value for a specific skill state from its schema."""
    try:
        schema = load_skill_schema(skill_name)
        if (
            schema
            and "properties" in schema
            and "states" in schema["properties"]
            and "properties" in schema["properties"]["states"]
            and state_name in schema["properties"]["states"]["properties"]
        ):
            state_config = schema["properties"]["states"]["properties"][state_name]

            # Return the default value if specified
            if "default" in state_config:
                return state_config["default"]

            # If no default, use the first valid enum value
            if "enum" in state_config and state_config["enum"]:
                return state_config["enum"][0]

        # Fallback to "private"
        return "private"

    except Exception as e:
        logger.warning(f"Error getting default for {skill_name}.{state_name}: {e}")
        return "private"


def get_skill_default_api_key_provider(skill_name: str) -> str:
    """Get the default API key provider for a skill from its schema."""
    try:
        schema = load_skill_schema(skill_name)
        if (
            schema
            and "properties" in schema
            and "api_key_provider" in schema["properties"]
        ):
            api_key_provider = schema["properties"]["api_key_provider"]

            # Return the default value if specified
            if "default" in api_key_provider:
                return api_key_provider["default"]

            # If no default, prefer platform if available
            if "enum" in api_key_provider and api_key_provider["enum"]:
                if "platform" in api_key_provider["enum"]:
                    return "platform"
                return api_key_provider["enum"][0]

        # Fallback to "platform"
        return "platform"

    except Exception as e:
        logger.warning(f"Error getting API key provider default for {skill_name}: {e}")
        return "platform"


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


def merge_autonomous_skills(
    skills_config: Dict[str, Any], autonomous_skills: List[str]
) -> Dict[str, Any]:
    """Merge autonomous skills into existing skills configuration.

    Args:
     skills_config: Existing skills configuration
     autonomous_skills: List of skill names required for autonomous tasks

    Returns:
     Updated skills configuration with autonomous skills added
    """
    if not autonomous_skills:
        logger.debug(" No autonomous skills to merge")
        return skills_config

    logger.info(
        f"Merging {len(autonomous_skills)} autonomous skills: {autonomous_skills}"
    )
    logger.debug(f"Input skills config keys: {list(skills_config.keys())}")

    for skill_name in autonomous_skills:
        if skill_name not in skills_config:
            # Add required autonomous skills with dynamic configuration
            skill_states = get_skill_states(skill_name)
            logger.debug(
                f"Got {len(skill_states)} states for {skill_name}: {skill_states}"
            )

            if not skill_states:
                logger.warning(f"No states found for autonomous skill: {skill_name}")
                continue

            states_dict = {}
            for state in skill_states:
                states_dict[state] = get_skill_state_default(skill_name, state)

            skills_config[skill_name] = {
                "enabled": True,
                "states": states_dict,
                "api_key_provider": get_skill_default_api_key_provider(skill_name),
            }
            logger.info(
                f"Added autonomous skill: {skill_name} (with {len(skill_states)} states)"
            )
        else:
            # Ensure autonomous skills are enabled
            skills_config[skill_name]["enabled"] = True
            logger.info(f"Enabled existing skill for autonomous use: {skill_name}")

    logger.debug(f"Output skills config keys: {list(skills_config.keys())}")
    return skills_config


def get_skill_mapping() -> Dict[str, Dict[str, Set[str]]]:
    """Generate skill mapping dynamically from actual skill implementations."""
    mapping = {}
    all_real_skills = get_all_real_skills()

    # Build mapping from configuration
    for skill_name, keywords in get_skill_keyword_config().items():
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
        if skill_name not in get_skill_keyword_config() and skill_name not in mapping:
            mapping[skill_name] = {skill_name: skill_states}

    return mapping


def add_skill_by_name(prompt: str, skills_config: Dict[str, Any]) -> Dict[str, Any]:
    """Add skills mentioned by exact name in the prompt."""
    all_real_skills = get_all_real_skills()
    prompt_lower = prompt.lower()

    # Check for exact skill name matches
    for skill_name in all_real_skills.keys():
        if skill_name in prompt_lower:
            # Get states with schema-based defaults
            states_dict = {}
            for state in all_real_skills[skill_name]:
                states_dict[state] = get_skill_state_default(skill_name, state)

            skills_config[skill_name] = {
                "enabled": True,
                "states": states_dict,
                "api_key_provider": get_skill_default_api_key_provider(skill_name),
            }

    # Handle "add all X skills" pattern
    if "add all" in prompt_lower:
        for skill_name in all_real_skills.keys():
            if f"all {skill_name}" in prompt_lower:
                # Get states with schema-based defaults
                states_dict = {}
                for state in all_real_skills[skill_name]:
                    states_dict[state] = get_skill_state_default(skill_name, state)

                skills_config[skill_name] = {
                    "enabled": True,
                    "states": states_dict,
                    "api_key_provider": get_skill_default_api_key_provider(skill_name),
                }

    return skills_config


async def validate_skills_exist(skills_config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that all skills in the config actually exist in IntentKit.

    Args:
     skills_config: Skills configuration to validate

    Returns:
     Validated skills configuration with only existing skills
    """
    logger.debug(f"Validating skills exist - input: {list(skills_config.keys())}")
    logger.debug(f"Available skill categories: {list(AVAILABLE_SKILL_CATEGORIES)}")

    validated_skills = {}

    for skill_name, skill_config in skills_config.items():
        if skill_name in AVAILABLE_SKILL_CATEGORIES:
            validated_skills[skill_name] = skill_config
            logger.debug(f"Skill {skill_name} exists and validated")
        else:
            logger.warning(
                f"Skipping non-existent skill '{skill_name}' - only available skills: {list(AVAILABLE_SKILL_CATEGORIES)}"
            )

    logger.debug(f"Validated skills output: {list(validated_skills.keys())}")
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
    agent_owner_skills = get_agent_owner_api_key_skills()
    configurable_skills = get_configurable_api_key_skills()

    for skill_name, skill_config in skills_config.items():
        # Skip skills that always require agent owner API keys
        if skill_name in agent_owner_skills:
            logger.info(
                f"Excluding skill '{skill_name}' from auto-generation: requires agent owner API key"
            )
            continue

        # For configurable skills, ensure we set api_key_provider to platform
        skill_config = skill_config.copy()
        if skill_name in configurable_skills:
            skill_config["api_key_provider"] = "platform"
        else:
            # For other skills, use the schema default
            skill_config["api_key_provider"] = get_skill_default_api_key_provider(
                skill_name
            )

        filtered_skills[skill_name] = skill_config

    return filtered_skills


async def identify_skills(
    prompt: str, client: OpenAI, llm_logger: Optional["LLMLogger"] = None
) -> Dict[str, Any]:
    """Identify relevant skills from the prompt using only real skill data.

    Args:
     prompt: The natural language prompt
     client: OpenAI client (not used, kept for compatibility)
     llm_logger: Optional LLM logger for tracking API calls (not used in this implementation)

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
                    # Get states with schema-based defaults
                    states_dict = {}
                    for state in states:
                        states_dict[state] = get_skill_state_default(skill_name, state)

                    skills_config[skill_name] = {
                        "enabled": True,
                        "states": states_dict,
                        "api_key_provider": get_skill_default_api_key_provider(
                            skill_name
                        ),
                    }
                else:
                    # Merge states if skill already exists
                    existing_states = skills_config[skill_name]["states"]
                    for state in states:
                        if state not in existing_states:
                            existing_states[state] = get_skill_state_default(
                                skill_name, state
                            )

    return skills_config
