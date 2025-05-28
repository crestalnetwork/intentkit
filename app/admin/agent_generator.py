"""Agent Generator Module.

This module provides functionality to generate agent schemas from natural language prompts
using OpenAI's API, with validation against IntentKit's JSON schema.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import jsonref
import jsonschema
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config.config import config
from models.agent import Agent, AgentCreate, AgentUpdate

logger = logging.getLogger(__name__)

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Path to agent schema
AGENT_SCHEMA_PATH = PROJECT_ROOT / "models" / "agent_schema.json"

# Simplified mapping of capability keywords to IntentKit skills
SKILL_MAPPING = {
    # Web & Research
    "search": {"tavily": ["tavily_search"]},
    "web": {"tavily": ["tavily_search"]},
    "research": {"tavily": ["tavily_search"]},
    "extract": {"tavily": ["tavily_extract"]},
    # Social Media
    "twitter": {"twitter": ["post_tweet", "search_tweets"]},
    "tweet": {"twitter": ["post_tweet"]},
    "slack": {"slack": ["post_message"]},
    "telegram": {"telegram": ["post_message"]},
    # Crypto & DeFi
    "crypto": {"cryptocompare": ["get_price"]},
    "token": {"cryptocompare": ["get_price"]},
    "defi": {"defillama": ["get_protocol", "get_tvl"]},
    "dex": {"dexscreener": ["search_pairs"]},
    "dune": {"dune_analytics": ["query"]},
    "analytics": {"dapplooker": ["query"]},
    # Blockchain
    "wallet": {"cdp": ["get_balance", "transfer"]},
    "blockchain": {"cdp": ["get_balance"]},
    "portfolio": {"portfolio": ["get_portfolio"]},
    "moralis": {"moralis": ["get_token_price"]},
    # Development
    "github": {"github": ["search_repositories"]},
    "git": {"github": ["search_repositories"]},
    # Media Generation
    "image": {"venice_image": ["generate_image"]},
    "speech": {"unrealspeech": ["create_speech"]},
    "vision": {"openai": ["vision"]},
    # Utilities
    "time": {"common": ["current_time"]},
    "weather": {"common": ["weather"]},
    "random": {"common": ["random"]},
}

# List of allowed models
ALLOWED_MODELS = ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4o-mini"]


class ValidationResult(BaseModel):
    """Result of schema validation."""

    valid: bool = Field(..., description="Whether the schema is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")


async def get_agent_schema() -> Dict[str, Any]:
    """Get the agent schema with all references resolved.

    Returns:
        The complete JSON schema for the Agent model
    """
    base_uri = f"file://{AGENT_SCHEMA_PATH}"
    with open(AGENT_SCHEMA_PATH) as f:
        schema = jsonref.load(f, base_uri=base_uri, proxies=False, lazy_load=False)

    return schema


async def validate_schema(data: Dict[str, Any]) -> ValidationResult:
    """Validate a schema against the agent schema.

    Args:
        data: The schema to validate

    Returns:
        ValidationResult with validation status and errors
    """
    schema = await get_agent_schema()
    result = ValidationResult(valid=True)

    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.exceptions.ValidationError as e:
        result.valid = False
        # Extract concise error information instead of the full error
        error_msg = _format_validation_error(e)
        result.errors.append(error_msg)

    return result


def _format_validation_error(error: jsonschema.exceptions.ValidationError) -> str:
    """Format a jsonschema validation error into a concise, user-friendly message."""
    field_path = (
        ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
    )

    if error.validator == "required":
        return f"Missing required fields: {', '.join(error.validator_value)}"

    elif error.validator == "additionalProperties":
        if "were unexpected" in error.message:
            match = re.search(r"\(([^)]+) were unexpected\)", error.message)
            if match:
                unexpected = match.group(1).replace("'", "").replace(" ", "")
                return f"Unexpected properties: {unexpected}"
        return "Schema contains unexpected properties"

    elif error.validator == "type":
        return f"Field '{field_path}' should be {error.validator_value}, got {type(error.instance).__name__}"

    elif error.validator in ["maxLength", "minLength"]:
        limit = error.validator_value
        actual = len(error.instance) if error.instance else 0
        op = "max" if error.validator == "maxLength" else "min"
        return f"Field '{field_path}' length invalid ({op} {limit}, got {actual})"

    elif error.validator == "enum":
        return f"Field '{field_path}' must be one of: {', '.join(str(v) for v in error.validator_value)}"

    elif error.validator == "pattern":
        return f"Field '{field_path}' does not match required pattern"

    else:
        return f"Validation error in '{field_path}': {error.message.split('.')[0]}"


async def validate_agent_create(
    agent_data: Dict[str, Any], user_id: Optional[str] = None
) -> ValidationResult:
    """Validate agent data using the same validation as the admin API.

    Args:
        agent_data: The agent data to validate
        user_id: Optional user ID for authorization check

    Returns:
        ValidationResult with validation status and errors
    """
    result = ValidationResult(valid=True)

    try:
        # Create AgentUpdate from data
        agent = AgentUpdate.model_validate(agent_data)

        # Validate owner
        if not agent.owner:
            result.valid = False
            result.errors.append("Owner is required")
            return result

        # Validate fee percentage if user_id is provided
        max_fee = 100
        if user_id:
            if agent.owner != user_id:
                result.valid = False
                result.errors.append("Owner does not match user ID")
                return result

        # Validate fee percentage
        if agent.fee_percentage and agent.fee_percentage > max_fee:
            result.valid = False
            result.errors.append("Fee percentage too high")
            return result

        # Validate autonomous schedule
        try:
            agent.validate_autonomous_schedule()
        except ValueError as e:
            result.valid = False
            result.errors.append(str(e))

    except ValidationError as e:
        result.valid = False
        for error in e.errors():
            result.errors.append(f"{error['loc'][0]}: {error['msg']}")

    return result


async def generate_agent_schema(
    prompt: str,
    model_override: Optional[str] = None,
    temperature_override: Optional[float] = None,
    user_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], Set[str]]:
    """Generate an agent schema from a natural language prompt.

    Args:
        prompt: The natural language prompt describing the agent
        model_override: Optional model override
        temperature_override: Optional temperature override
        user_id: Optional user ID for validation

    Returns:
        A tuple of (schema, identified_skills)
    """
    # Get OpenAI API key from config
    api_key = config.openai_api_key
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in configuration")

    # Create OpenAI client
    client = OpenAI(api_key=api_key)

    # Identify relevant skills from the prompt
    skills_config = await identify_skills(prompt, client)

    # Get identified skills
    identified_skills = set(skills_config.keys())

    # Generate agent attributes
    attributes = await generate_agent_attributes(prompt, skills_config, client)

    # Set model to one of the allowed models
    model = model_override or "gpt-4.1-nano"
    if model not in ALLOWED_MODELS:
        model = "gpt-4.1-nano"

    # Combine into full schema
    schema = {
        **attributes,
        "skills": skills_config,
        "model": model,
        "temperature": temperature_override or 0.7,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }

    # If user_id is provided, set owner
    if user_id:
        schema["owner"] = user_id

    # Validate the schema
    schema_validation = await validate_schema(schema)
    if not schema_validation.valid:
        logger.warning(
            f"Generated schema failed validation: {schema_validation.errors}"
        )
        # Attempt to fix the schema based on validation errors
        schema = await fix_validation_errors(schema, schema_validation.errors, [])

    # Validate with agent create validation
    agent_validation = await validate_agent_create(schema, user_id)
    if not agent_validation.valid:
        logger.warning(
            f"Generated schema failed agent validation: {agent_validation.errors}"
        )
        # Attempt to fix agent validation issues
        schema = await fix_validation_errors(schema, [], agent_validation.errors)

    return schema, identified_skills


async def fix_validation_errors(
    schema: Dict[str, Any], schema_errors: List[str], agent_errors: List[str]
) -> Dict[str, Any]:
    """Attempt to fix validation errors.

    Args:
        schema: The original schema
        schema_errors: Schema validation errors
        agent_errors: Agent validation errors

    Returns:
        Fixed schema
    """
    fixed_schema = schema.copy()

    # Fix required fields
    required_fields = ["name", "purpose", "personality", "principles"]
    for field in required_fields:
        if field not in fixed_schema or not fixed_schema[field]:
            fixed_schema[field] = f"Default {field.capitalize()}"

    # Fix model and temperature
    if "model" not in fixed_schema or fixed_schema["model"] not in ALLOWED_MODELS:
        fixed_schema["model"] = "gpt-4.1-nano"
    if "temperature" not in fixed_schema or not (0 <= fixed_schema["temperature"] <= 2):
        fixed_schema["temperature"] = 0.7

    # Fix agent-specific issues
    if "Owner is required" in agent_errors:
        fixed_schema["owner"] = "system"
    if "Fee percentage too high" in agent_errors and "fee_percentage" in fixed_schema:
        fixed_schema["fee_percentage"] = 100
    if (
        any("autonomous" in error for error in agent_errors)
        and "autonomous" in fixed_schema
    ):
        fixed_schema.pop("autonomous")

    return fixed_schema


async def identify_skills(prompt: str, client: OpenAI) -> Dict[str, Any]:
    """Identify relevant skills from the prompt.

    Args:
        prompt: The natural language prompt
        client: OpenAI client

    Returns:
        Dict containing skill configurations
    """
    # First attempt: Use keyword matching for common capabilities
    skills_config = keyword_match_skills(prompt)

    # If no skills found or for more complex prompts, use OpenAI
    if not skills_config:
        skills_config = await openai_match_skills(prompt, client)

    return skills_config


def keyword_match_skills(prompt: str) -> Dict[str, Any]:
    """Match skills using keyword matching.

    Args:
        prompt: The natural language prompt

    Returns:
        Dict containing skill configurations
    """
    skills_config = {}
    prompt_lower = prompt.lower()

    for keyword, skill_mapping in SKILL_MAPPING.items():
        if keyword.lower() in prompt_lower:
            for skill_name, states in skill_mapping.items():
                if skill_name not in skills_config:
                    skills_config[skill_name] = {"enabled": True, "states": {}}

                for state in states:
                    skills_config[skill_name]["states"][state] = "public"

    # Apply proper skill configurations
    return apply_skill_defaults(skills_config)


def apply_skill_defaults(skills_config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply default configurations for skills that require additional fields."""
    # Skills requiring api_key_provider
    api_key_provider_skills = {
        "tavily",
        "twitter",
        "slack",
        "telegram",
        "cryptocompare",
        "cryptopanic",
        "dexscreener",
        "defillama",
        "github",
        "moralis",
        "unrealspeech",
        "venice_image",
        "openai",
        "chainlist",
        "token",
    }

    # Skills requiring direct api_key
    direct_api_key_skills = {
        "dune_analytics": {"api_key": ""},
        "dapplooker": {"api_key": ""},
    }

    for skill_name, skill_config in skills_config.items():
        if skill_name in api_key_provider_skills:
            skill_config["api_key_provider"] = "platform"
        elif skill_name in direct_api_key_skills:
            skill_config.update(direct_api_key_skills[skill_name])

    return skills_config


async def openai_match_skills(prompt: str, client: OpenAI) -> Dict[str, Any]:
    """Match skills using OpenAI's API."""
    system_prompt = """Identify IntentKit skills needed for an agent based on the prompt.

Available skills: tavily (web search), twitter, slack, telegram, cryptocompare (crypto data), 
cryptopanic (crypto news), dexscreener (DEX pairs), defillama (DeFi), dune_analytics, 
dapplooker, cdp (blockchain wallet), github, portfolio, token, moralis, chainlist, 
unrealspeech (TTS), venice_image (image gen), openai (vision), common (utilities).

Return JSON with enabled skills and their public states. Example:
{"tavily": {"enabled": true, "states": {"tavily_search": "public"}}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Prompt: {prompt}"},
            ],
            temperature=0.2,
        )
        skills_config = json.loads(response.choices[0].message.content)
        return apply_skill_defaults(skills_config)
    except Exception as e:
        logger.error(f"Error in openai_match_skills: {e}")
        return {}


async def generate_agent_attributes(
    prompt: str, skills_config: Dict[str, Any], client: OpenAI
) -> Dict[str, Any]:
    """Generate agent attributes based on the prompt."""
    system_prompt = """Generate agent attributes from the prompt:
- name: Concise name (max 50 chars)
- purpose: Clear purpose statement (1-3 paragraphs)  
- personality: Character traits (1-2 paragraphs)
- principles: Core values (1-2 paragraphs)
- description: Brief public description (1-3 sentences)

Return JSON format."""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Prompt: {prompt}\nSkills: {', '.join(skills_config.keys())}",
                },
            ],
            temperature=0.7,
        )
        attributes = json.loads(response.choices[0].message.content)
        attributes["name"] = attributes.get("name", "")[:50]
        attributes["owner"] = "system"
        return attributes
    except Exception as e:
        logger.error(f"Error in generate_agent_attributes: {e}")
        return {
            "name": "Generated Agent",
            "purpose": "This agent was automatically generated based on a natural language prompt.",
            "personality": "Helpful, friendly, and informative.",
            "principles": "Accuracy, usefulness, and respect for user needs.",
            "description": "An AI assistant created from a natural language prompt.",
            "owner": "system",
        }


async def create_agent_from_schema(schema: Dict[str, Any]) -> str:
    """Create a new agent from a generated schema.

    Args:
        schema: The agent schema

    Returns:
        The ID of the created agent
    """
    # Create AgentCreate from schema
    agent_create = AgentCreate.model_validate(schema)

    # Create agent
    agent = await agent_create.create()

    return agent.id


async def update_agent_from_schema(agent_id: str, schema: Dict[str, Any]) -> None:
    """Update an existing agent with a generated schema.

    Args:
        agent_id: The ID of the agent to update
        schema: The new agent schema
    """
    # Create AgentUpdate from schema
    agent_update = AgentUpdate.model_validate(schema)

    # Update agent
    await agent_update.update(agent_id)


async def get_existing_agent_schema(agent_id: str) -> Dict[str, Any]:
    """Get the schema of an existing agent.

    Args:
        agent_id: The ID of the agent

    Returns:
        The agent schema
    """
    agent = await Agent.get(agent_id)
    if not agent:
        raise ValueError(f"Agent with ID {agent_id} not found")

    return agent.model_dump(exclude_unset=True)
