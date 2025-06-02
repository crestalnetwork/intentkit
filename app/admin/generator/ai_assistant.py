"""AI Assistant Module.

This module handles all AI-powered operations for agent generation including:
- Agent enhancement and updates using LLM
- Attribute generation from prompts
- AI-powered error correction and schema fixing
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from openai import OpenAI

from app.config.config import config
from models.agent import AgentUpdate
from models.generator import (
    AgentGenerationLog,
    AgentGenerationLogCreate,
)
from models.db import get_session

from .skill_processor import (
    AVAILABLE_SKILL_CATEGORIES,
    filter_skills_for_auto_generation,
    identify_skills,
)
from .validation import (
    validate_agent_create,
    validate_schema,
)

logger = logging.getLogger(__name__)

# List of allowed models - Updated to match schema
ALLOWED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1-nano",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o4-mini",
    "deepseek-chat",
    "grok-2",
    "grok-3",
    "grok-3-mini",
    "eternalai",
    "reigent",
    "venice-uncensored",
    "venice-llama-4-maverick-17b",
]


def _extract_token_usage(response) -> Dict[str, Any]:
    """Extract token usage information from OpenAI response.
    
    Args:
        response: OpenAI API response
        
    Returns:
        Dict containing token usage information
    """
    usage_info = {
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "input_tokens_details": None,
        "completion_tokens_details": None,
    }
    
    if hasattr(response, "usage") and response.usage:
        usage = response.usage
        usage_info["total_tokens"] = getattr(usage, "total_tokens", 0)
        usage_info["input_tokens"] = getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0)
        usage_info["output_tokens"] = getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0)
        
        # Get detailed token information if available
        if hasattr(usage, "input_tokens_details") and usage.input_tokens_details:
            usage_info["input_tokens_details"] = usage.input_tokens_details.__dict__ if hasattr(usage.input_tokens_details, "__dict__") else dict(usage.input_tokens_details)
            
        if hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details:
            usage_info["completion_tokens_details"] = usage.completion_tokens_details.__dict__ if hasattr(usage.completion_tokens_details, "__dict__") else dict(usage.completion_tokens_details)
    
    return usage_info


async def enhance_agent(
    prompt: str,
    existing_agent: "AgentUpdate",
    client: OpenAI,
    user_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], Set[str], Dict[str, Any]]:
    """Generate minimal updates to an existing agent based on a prompt.

    This function preserves the existing agent configuration and only makes
    targeted changes based on the prompt, ensuring stability and user customizations.

    Args:
        prompt: The natural language prompt describing desired changes
        existing_agent: The current agent configuration
        client: OpenAI client for API calls
        user_id: Optional user ID for validation

    Returns:
        A tuple of (updated_schema, identified_skills, token_usage)
    """
    logger.info("Generating minimal agent update based on existing configuration")

    # Initialize token usage tracking
    total_token_usage = {
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "input_tokens_details": None,
        "completion_tokens_details": None,
    }

    # Convert existing agent to dictionary format
    existing_schema = existing_agent.model_dump(exclude_unset=True)

    # Get current skills for context
    current_skills = existing_schema.get("skills", {})
    current_skill_names = [
        skill
        for skill, config in current_skills.items()
        if config.get("enabled", False)
    ]

    # Use the real skill processor to identify skills from prompt
    # This ensures we only get real skill states, not AI-generated fake ones
    identified_skills_config = await identify_skills(prompt, client)
    identified_skill_names = set(identified_skills_config.keys())

    logger.info(f"Real skills identified from prompt: {identified_skill_names}")

    # Start with existing configuration
    updated_schema = existing_schema.copy()

    # Ensure model field is present (required field)
    if "model" not in updated_schema or not updated_schema["model"]:
        updated_schema["model"] = "gpt-4.1-nano"  # Default model

    # Merge skills carefully - preserve existing, add new real skills
    existing_skills = updated_schema.get("skills", {})
    merged_skills = existing_skills.copy()

    # Add newly identified real skills
    for skill_name, skill_config in identified_skills_config.items():
        if skill_name not in merged_skills:
            # Add new skill with real states
            merged_skills[skill_name] = skill_config
            logger.info(
                f"Added new skill: {skill_name} with real states: {list(skill_config.get('states', {}).keys())}"
            )
        else:
            # Enable existing skill if it was disabled, and merge states
            existing_skill = merged_skills[skill_name]
            if not existing_skill.get("enabled", False):
                merged_skills[skill_name] = skill_config
                logger.info(f"Enabled existing skill: {skill_name}")
            else:
                # Merge states from both existing and new
                existing_states = existing_skill.get("states", {})
                new_states = skill_config.get("states", {})
                merged_states = {**existing_states, **new_states}
                merged_skills[skill_name]["states"] = merged_states
                logger.info(f"Merged states for skill: {skill_name}")

    updated_schema["skills"] = merged_skills

    # Filter skills for auto-generation (remove agent-owner API key skills)
    updated_schema["skills"] = await filter_skills_for_auto_generation(
        updated_schema["skills"]
    )

    # Set user ID if provided
    if user_id:
        updated_schema["owner"] = user_id

    # Only update agent attributes (name, purpose, etc.) if the prompt specifically asks for them
    # Use AI only for these text fields, NOT for skills
    should_update_attributes = any(
        keyword in prompt.lower()
        for keyword in [
            "name",
            "purpose",
            "personality",
            "principle",
            "description",
            "change",
            "update",
            "modify",
            "rename",
        ]
    )

    if should_update_attributes:
        logger.info("Updating agent attributes using AI (not skills)")
        # Use AI only for text attributes, never for skills
        attr_system_prompt = f"""Update only the text attributes (name, purpose, personality, principles, description) of this agent based on the user request.

IMPORTANT: 
- DO NOT include "skills" in your response
- Only update the text fields requested by the user
- Keep existing values for fields not mentioned in the request
- Return only the fields that need to be changed

Current agent:
{json.dumps({k: v for k, v in existing_schema.items() if k != "skills"}, indent=2)}

User request: {prompt}

Return JSON with only the text fields that need updates."""

        try:
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": attr_system_prompt},
                    {"role": "user", "content": f"Update request: {prompt}"},
                ],
                temperature=0.2,
            )

            # Extract and accumulate token usage
            token_usage = _extract_token_usage(response)
            total_token_usage["total_tokens"] += token_usage["total_tokens"]
            total_token_usage["input_tokens"] += token_usage["input_tokens"]
            total_token_usage["output_tokens"] += token_usage["output_tokens"]
            
            # Store the first detailed token info (if available)
            if not total_token_usage["input_tokens_details"] and token_usage["input_tokens_details"]:
                total_token_usage["input_tokens_details"] = token_usage["input_tokens_details"]
            if not total_token_usage["completion_tokens_details"] and token_usage["completion_tokens_details"]:
                total_token_usage["completion_tokens_details"] = token_usage["completion_tokens_details"]

            attr_updates = json.loads(response.choices[0].message.content)
            # Apply attribute updates (but never skills)
            for key, value in attr_updates.items():
                if key != "skills":  # Never allow AI to update skills
                    updated_schema[key] = value
                    logger.info(f"Updated attribute: {key}")

        except Exception as e:
            logger.error(f"Error updating attributes with AI: {e}")

    # Ensure required fields exist with fallbacks from existing agent
    required_fields = ["name", "purpose", "personality", "principles"]
    for field in required_fields:
        if field not in updated_schema or not updated_schema[field]:
            # Keep existing value or use a default
            if field in existing_schema and existing_schema[field]:
                updated_schema[field] = existing_schema[field]
            else:
                updated_schema[field] = f"Updated {field.capitalize()}"

    # Combine current skills with newly identified skills
    all_identified_skills = set(current_skill_names) | identified_skill_names

    logger.info(
        f"Final skills after update: {list(updated_schema.get('skills', {}).keys())}"
    )
    logger.info(f"All identified skills: {all_identified_skills}")

    return updated_schema, all_identified_skills, total_token_usage


async def generate_agent_attributes(
    prompt: str, skills_config: Dict[str, Any], client: OpenAI
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generate agent attributes based on the prompt.
    
    Returns:
        A tuple of (attributes, token_usage)
    """
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
        
        # Extract token usage
        token_usage = _extract_token_usage(response)
        
        attributes = json.loads(response.choices[0].message.content)
        attributes["name"] = attributes.get("name", "")[:50]
        attributes["owner"] = "system"
        return attributes, token_usage
    except Exception as e:
        logger.error(f"Error in generate_agent_attributes: {e}")
        fallback_attributes = {
            "name": "Generated Agent",
            "purpose": "This agent was automatically generated based on a natural language prompt.",
            "personality": "Helpful, friendly, and informative.",
            "principles": "Accuracy, usefulness, and respect for user needs.",
            "description": "An AI assistant created from a natural language prompt.",
            "owner": "system",
        }
        fallback_token_usage = {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "input_tokens_details": None,
            "completion_tokens_details": None,
        }
        return fallback_attributes, fallback_token_usage


async def generate_validated_agent(
    prompt: str,
    user_id: Optional[str] = None,
    existing_agent: Optional["AgentUpdate"] = None,
    max_attempts: int = 3,
) -> Tuple[Dict[str, Any], Set[str]]:
    """Generate agent schema with automatic validation retry and AI self-correction.

    This function uses an iterative approach:
    1. Generate agent schema
    2. Validate it
    3. If validation fails, feed raw errors back to AI for self-correction
    4. Repeat until validation passes or max attempts reached

    Args:
        prompt: The natural language prompt describing the agent
        user_id: Optional user ID for validation
        existing_agent: Optional existing agent to update
        max_attempts: Maximum number of generation attempts

    Returns:
        A tuple of (validated_schema, identified_skills)
    """
    start_time = time.time()
    
    # Create generation log
    async with get_session() as session:
        log_data = AgentGenerationLogCreate(
            user_id=user_id,
            prompt=prompt,
            existing_agent_id=existing_agent.id if existing_agent else None,
            is_update=existing_agent is not None,
        )
        generation_log = await AgentGenerationLog.create(session, log_data)
    
    # Track cumulative metrics
    total_tokens_used = 0
    total_input_tokens = 0
    total_output_tokens = 0
    all_token_details = []
    
    # Get OpenAI API key from config
    api_key = config.openai_api_key
    if not api_key:
        error_msg = "OPENAI_API_KEY is not set in configuration"
        # Update log with error
        async with get_session() as session:
            await generation_log.update_completion(
                session=session,
                success=False,
                error_message=error_msg,
                generation_time_ms=int((time.time() - start_time) * 1000),
            )
        raise ValueError(error_msg)

    # Create OpenAI client
    client = OpenAI(api_key=api_key)

    last_schema = None
    last_errors = []
    identified_skills = set()

    try:
        for attempt in range(max_attempts):
            try:
                logger.info(f"Schema generation attempt {attempt + 1}/{max_attempts}")

                if attempt == 0:
                    # First attempt: Generate from scratch
                    from .agent_generator import generate_agent_schema

                    schema, skills, token_usage = await generate_agent_schema(
                        prompt=prompt,
                        user_id=user_id,
                        existing_agent=existing_agent,
                    )
                    last_schema = schema
                    identified_skills = skills
                    
                    # Accumulate token usage from first attempt
                    if token_usage:
                        total_tokens_used += token_usage["total_tokens"]
                        total_input_tokens += token_usage["input_tokens"]
                        total_output_tokens += token_usage["output_tokens"]
                        all_token_details.append(token_usage)
                else:
                    # Subsequent attempts: Let AI fix the validation errors
                    logger.info("Feeding validation errors to AI for self-correction")
                    schema, skills, token_usage = await fix_agent_schema_with_ai_logged(
                        original_prompt=prompt,
                        failed_schema=last_schema,
                        validation_errors=last_errors,
                        client=client,
                        user_id=user_id,
                        existing_agent=existing_agent,
                    )
                    last_schema = schema
                    identified_skills = identified_skills.union(skills)
                    
                    # Accumulate token usage
                    if token_usage:
                        total_tokens_used += token_usage["total_tokens"]
                        total_input_tokens += token_usage["input_tokens"]
                        total_output_tokens += token_usage["output_tokens"]
                        all_token_details.append(token_usage)

                # Validate the schema
                schema_validation = await validate_schema(schema)
                agent_validation = await validate_agent_create(schema, user_id)

                # Check if validation passed
                if schema_validation.valid and agent_validation.valid:
                    logger.info(f"Validation passed on attempt {attempt + 1}")
                    
                    # Update log with success
                    async with get_session() as session:
                        await generation_log.update_completion(
                            session=session,
                            generated_agent_schema=schema,
                            identified_skills=list(identified_skills),
                            openai_model="gpt-4.1-nano",
                            total_tokens=total_tokens_used,
                            input_tokens=total_input_tokens,
                            output_tokens=total_output_tokens,
                            input_tokens_details=all_token_details[0].get("input_tokens_details") if all_token_details else None,
                            completion_tokens_details=all_token_details[0].get("completion_tokens_details") if all_token_details else None,
                            generation_time_ms=int((time.time() - start_time) * 1000),
                            retry_count=attempt,
                            success=True,
                        )
                    
                    return schema, identified_skills

                # Collect raw validation errors for AI feedback
                last_errors = []
                if not schema_validation.valid:
                    last_errors.extend(
                        [f"Schema error: {error}" for error in schema_validation.errors]
                    )
                if not agent_validation.valid:
                    last_errors.extend(
                        [
                            f"Agent validation error: {error}"
                            for error in agent_validation.errors
                        ]
                    )

                logger.warning(
                    f"Attempt {attempt + 1} validation failed with {len(last_errors)} errors"
                )

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {str(e)}")
                last_errors = [f"Generation exception: {str(e)}"]

        # All attempts failed
        error_summary = "; ".join(last_errors[-5:])  # Last 5 errors for context
        error_message = f"Failed to generate valid agent schema after {max_attempts} attempts. Last errors: {error_summary}"
        
        # Update log with failure
        async with get_session() as session:
            await generation_log.update_completion(
                session=session,
                generated_agent_schema=last_schema,
                identified_skills=list(identified_skills),
                openai_model="gpt-4.1-nano",
                total_tokens=total_tokens_used,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                generation_time_ms=int((time.time() - start_time) * 1000),
                retry_count=max_attempts,
                validation_errors={"errors": last_errors},
                success=False,
                error_message=error_message,
            )
        
        raise ValueError(error_message)
        
    except Exception as e:
        # Update log with unexpected error
        async with get_session() as session:
            await generation_log.update_completion(
                session=session,
                generated_agent_schema=last_schema,
                identified_skills=list(identified_skills),
                openai_model="gpt-4.1-nano",
                total_tokens=total_tokens_used,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                generation_time_ms=int((time.time() - start_time) * 1000),
                retry_count=max_attempts,
                success=False,
                error_message=str(e),
            )
        raise


async def fix_agent_schema_with_ai_logged(
    original_prompt: str,
    failed_schema: Dict[str, Any],
    validation_errors: List[str],
    client: OpenAI,
    user_id: Optional[str] = None,
    existing_agent: Optional["AgentUpdate"] = None,
) -> Tuple[Dict[str, Any], Set[str], Dict[str, Any]]:
    """Use AI to fix validation errors in agent schema with token logging.

    This feeds the raw validation errors to AI and lets it understand and fix them automatically.

    Args:
        original_prompt: The original user prompt
        failed_schema: The schema that failed validation
        validation_errors: Raw validation error messages
        client: OpenAI client
        user_id: Optional user ID
        existing_agent: Optional existing agent for updates

    Returns:
        A tuple of (fixed_schema, identified_skills, token_usage)
    """
    # Prepare context for AI error correction
    error_context = "\n".join(validation_errors)

    # Valid models list for AI reference
    valid_models = ALLOWED_MODELS

    correction_prompt = f"""You are an expert at fixing IntentKit agent schemas. The schema below failed validation with specific errors.

ORIGINAL USER REQUEST: {original_prompt}

FAILED SCHEMA:
{json.dumps(failed_schema, indent=2)}

VALIDATION ERRORS:
{error_context}

Your task:
1. Analyze each validation error carefully
2. Fix the schema to resolve ALL validation errors
3. Maintain the original intent and functionality
4. Only use these valid models: {', '.join(valid_models)}
5. Ensure skills field is a proper dict with valid skill configurations
6. All required fields must be present and properly formatted

Return only the corrected schema as valid JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": correction_prompt},
                {
                    "role": "user",
                    "content": "Fix the validation errors and return the corrected schema.",
                },
            ],
            temperature=0.1,  # Very low temperature for precise error correction
        )

        # Extract token usage
        token_usage = _extract_token_usage(response)

        corrected_schema = json.loads(response.choices[0].message.content)
        logger.info("AI successfully generated error corrections")

        # Ensure model is set to a valid value if not already
        if (
            "model" not in corrected_schema
            or corrected_schema["model"] not in valid_models
        ):
            corrected_schema["model"] = "gpt-4.1-nano"
            logger.info("Explicitly set model to gpt-4.1-nano as fallback")

        # Extract skills for tracking
        skills_in_schema = set()
        if "skills" in corrected_schema and isinstance(
            corrected_schema["skills"], dict
        ):
            skills_in_schema = set(corrected_schema["skills"].keys())

        # Filter skills for auto-generation
        if "skills" in corrected_schema and isinstance(
            corrected_schema["skills"], dict
        ):
            corrected_schema["skills"] = await filter_skills_for_auto_generation(
                corrected_schema["skills"]
            )
        elif "skills" not in corrected_schema or not isinstance(
            corrected_schema["skills"], dict
        ):
            corrected_schema["skills"] = {}

        # Set user ID if provided
        if user_id:
            corrected_schema["owner"] = user_id

        return corrected_schema, skills_in_schema, token_usage

    except Exception as e:
        logger.error(f"AI error correction failed: {e}")
        # Fallback: return original schema with basic fixes
        fallback_schema = failed_schema.copy() if failed_schema is not None else {}

        # Apply basic required field fixes
        required_fields = ["name", "purpose", "personality", "principles"]
        for field in required_fields:
            if field not in fallback_schema or not fallback_schema[field]:
                fallback_schema[field] = f"Generated {field.capitalize()}"

        # Ensure model is valid
        fallback_schema["model"] = "gpt-4.1-nano"

        # Ensure skills is a dict
        if "skills" not in fallback_schema or not isinstance(
            fallback_schema["skills"], dict
        ):
            fallback_schema["skills"] = {}

        if user_id:
            fallback_schema["owner"] = user_id

        return fallback_schema, set(fallback_schema.get("skills", {}).keys()), {
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "input_tokens_details": None,
            "completion_tokens_details": None,
        }
