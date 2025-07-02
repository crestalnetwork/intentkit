"""Agent Generator Module.

Main orchestrator for AI-powered agent generation from natural language prompts.
This module coordinates the skill processing, validation, and AI assistance modules.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, Set, Tuple

from openai import OpenAI

from intentkit.config.config import config
from intentkit.models.agent import AgentUpdate

from .ai_assistant import (
    enhance_agent,
    generate_agent_attributes,
    generate_validated_agent,
)
from .autonomous_generator import generate_autonomous_configuration
from .skill_processor import (
    filter_skills_for_auto_generation,
    identify_skills,
    merge_autonomous_skills,
)

if TYPE_CHECKING:
    from .llm_logger import LLMLogger

logger = logging.getLogger(__name__)


async def generate_agent_schema(
    prompt: str,
    user_id: Optional[str] = None,
    existing_agent: Optional[AgentUpdate] = None,
    llm_logger: Optional["LLMLogger"] = None,
) -> Tuple[Dict[str, Any], Set[str], Dict[str, Any]]:
    """Generate agent schema from a natural language prompt.

    This is the main entry point for agent generation. It handles both new agent
    creation and existing agent updates with minimal changes.

    Args:
     prompt: Natural language description of the desired agent
     user_id: Optional user ID for ownership and validation
     existing_agent: Optional existing agent to update (preserves configuration)
     llm_logger: Optional LLM logger for tracking individual API calls

    Returns:
     A tuple of (agent_schema, identified_skills, token_usage)
    """
    logger.info(
        f"Generating agent schema from prompt: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'"
    )

    # Get OpenAI API key from config
    api_key = config.openai_api_key
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in configuration")

    # Create OpenAI client
    client = OpenAI(api_key=api_key)

    if existing_agent:
        # Update existing agent - preserves configuration, makes minimal changes
        logger.info(" Updating existing agent with minimal changes")
        schema, skills, token_usage = await enhance_agent(
            prompt=prompt,
            existing_agent=existing_agent,
            client=client,
            user_id=user_id,
            llm_logger=llm_logger,
        )
    else:
        # Create new agent from scratch
        logger.info(" Creating new agent from scratch")
        schema, skills, token_usage = await _generate_new_agent_schema(
            prompt=prompt,
            client=client,
            user_id=user_id,
            llm_logger=llm_logger,
        )

    logger.info(f"Generated agent schema with {len(skills)} skills: {list(skills)}")
    return schema, skills, token_usage


async def _generate_new_agent_schema(
    prompt: str,
    client: OpenAI,
    user_id: Optional[str] = None,
    llm_logger: Optional["LLMLogger"] = None,
) -> Tuple[Dict[str, Any], Set[str], Dict[str, Any]]:
    """Generate a completely new agent schema from a prompt.

    Args:
     prompt: Natural language prompt
     client: OpenAI client
     user_id: Optional user ID
     llm_logger: Optional LLM logger for tracking API calls

    Returns:
     A tuple of (agent_schema, identified_skills, token_usage)
    """
    # Step 1: Check for autonomous patterns first
    logger.info(" Step 1: Checking for autonomous task patterns")
    autonomous_result = await generate_autonomous_configuration(
        prompt, client, llm_logger=llm_logger
    )

    autonomous_configs = []
    autonomous_skills = []
    if autonomous_result:
        autonomous_configs, autonomous_skills = autonomous_result
        logger.info(f"Generated {len(autonomous_configs)} autonomous tasks")
        logger.info(f"Autonomous tasks require skills: {autonomous_skills}")
    else:
        logger.info(
            " No autonomous patterns detected, proceeding with standard agent generation"
        )

    # Step 2: Identify required skills from the prompt
    logger.info(" Step 2: Identifying skills from prompt")
    skills_config = await identify_skills(prompt, client, llm_logger=llm_logger)

    # Merge autonomous skills with identified skills
    if autonomous_skills:
        logger.info(
            f"Merging {len(autonomous_skills)} autonomous skills with identified skills"
        )
        skills_config = merge_autonomous_skills(skills_config, autonomous_skills)

    # Filter out skills that require agent owner API keys
    skills_config = await filter_skills_for_auto_generation(skills_config)

    logger.info(f"Final identified skills: {list(skills_config.keys())}")

    # Step 3: Generate agent attributes (name, purpose, personality, etc.)
    logger.info(" Step 3: Generating agent attributes")
    attributes, token_usage = await generate_agent_attributes(
        prompt, skills_config, client, llm_logger=llm_logger, user_id=user_id
    )

    # Step 4: Combine into complete agent schema
    logger.info(" Step 4: Assembling complete agent schema")
    schema = {
        **attributes,
        "skills": skills_config,
        "model": "gpt-4.1-nano",  # Default model
        "temperature": 0.7,
    }

    # Add autonomous configuration if detected
    if autonomous_configs:
        schema["autonomous"] = [config.model_dump() for config in autonomous_configs]
        logger.info(
            f"Added {len(autonomous_configs)} autonomous configurations to schema"
        )

        # Log details of each autonomous task
        for config in autonomous_configs:
            schedule_info = (
                f"{config.minutes} minutes" if config.minutes else config.cron
            )
            logger.info(f"Task: '{config.name}' - {schedule_info}")

    # Set user ID if provided
    if user_id:
        schema["owner"] = user_id
        logger.debug(f"Set agent owner: {user_id}")

    identified_skills = set(skills_config.keys())
    autonomous_count = len(autonomous_configs)
    logger.info(
        f"New agent schema generated with {len(identified_skills)} skills and {autonomous_count} autonomous tasks"
    )

    return schema, identified_skills, token_usage


# Main generation function with validation and self-correction
async def generate_validated_agent_schema(
    prompt: str,
    user_id: Optional[str] = None,
    existing_agent: Optional[AgentUpdate] = None,
    llm_logger: Optional["LLMLogger"] = None,
) -> Tuple[Dict[str, Any], Set[str], str]:
    """Generate and validate agent schema with summary.

    Args:
     prompt: Natural language description of the desired agent
     user_id: Optional user ID for ownership and validation
     existing_agent: Optional existing agent to update
     llm_logger: Optional LLM logger for tracking individual API calls

    Returns:
     A tuple of (agent_schema, identified_skills, summary_message)
    """
    return await generate_validated_agent(
        prompt=prompt,
        user_id=user_id,
        existing_agent=existing_agent,
        llm_logger=llm_logger,
    )
