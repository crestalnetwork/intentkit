"""AI Assistant Module.

This module handles core AI operations for agent generation including:
- Agent enhancement and updates using LLM
- Attribute generation from prompts  
- AI-powered error correction and schema fixing
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from openai import OpenAI

from app.config.config import config
from models.agent import AgentUpdate
from models.db import get_session
from models.generator import (
    AgentGenerationLog,
    AgentGenerationLogCreate,
)

from .llm_logger import get_conversation_history
from .skill_processor import (
    filter_skills_for_auto_generation,
    identify_skills,
)
from .utils import extract_token_usage, generate_agent_summary
from .validation import (
    validate_agent_create,
    validate_schema,
)

if TYPE_CHECKING:
    from .llm_logger import LLMLogger

logger = logging.getLogger(__name__)


async def enhance_agent(
    prompt: str,
    existing_agent: "AgentUpdate",
    client: OpenAI,
    user_id: Optional[str] = None,
    llm_logger: Optional["LLMLogger"] = None,
) -> Tuple[Dict[str, Any], Set[str], Dict[str, Any]]:
    """Generate minimal updates to an existing agent based on a prompt.

    This function preserves the existing agent configuration and only makes
    targeted changes based on the prompt, ensuring stability and user customizations.

    Args:
        prompt: The natural language prompt describing desired changes
        existing_agent: The current agent configuration
        client: OpenAI client for API calls
        user_id: Optional user ID for validation
        llm_logger: Optional LLM logger for tracking API calls

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

    # Use the real skill processor to identify skills from prompt
    identified_skills_config = await identify_skills(prompt, client, llm_logger=llm_logger)
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
            merged_skills[skill_name] = skill_config
            logger.info(f"Added new skill: {skill_name}")
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

    # Only update agent attributes if the prompt specifically asks for them
    should_update_attributes = any(
        keyword in prompt.lower()
        for keyword in [
            "name", "purpose", "personality", "principle", "description",
            "rename", "change name", "update name", "modify purpose",
            "change purpose", "update personality", "change personality",
        ]
    )

    if should_update_attributes:
        logger.info("Prompt requests attribute updates - using AI for text fields only")

        # Get conversation history if logger has a project_id
        history_messages = []
        if llm_logger:
            try:
                history_messages = await get_conversation_history(
                    project_id=llm_logger.request_id,
                    user_id=llm_logger.user_id,
                )
            except Exception as e:
                logger.warning(f"Failed to get conversation history: {e}")
                history_messages = []

        # Prepare system message for agent attribute updates
        system_message = {
            "role": "system",
            "content": f"""You are updating an existing agent's text attributes only. 
            
CRITICAL INSTRUCTIONS:
1. Only update name, purpose, personality, and principles based on the prompt
2. Keep all existing skills exactly as they are - DO NOT modify skills
3. Keep the existing model and temperature settings
4. Only make changes if the prompt specifically requests them
5. Return the complete agent schema as valid JSON

The agent currently has these attributes:
- Name: {updated_schema.get("name", "Unnamed Agent")}
- Purpose: {updated_schema.get("purpose", "No purpose defined")}
- Personality: {updated_schema.get("personality", "No personality defined")} 
- Principles: {updated_schema.get("principles", "No principles defined")}

Make minimal changes based on the prompt. If this is part of an ongoing conversation, consider the previous context.""",
        }

        # Build messages with conversation history
        messages = [system_message]
        
        # Add conversation history if available
        if history_messages:
            logger.info(f"Using {len(history_messages)} messages from conversation history for update")
            messages.extend(history_messages)
        
        # Add current request
        messages.append({
            "role": "user",
            "content": f"Update request: {prompt}\n\nCurrent agent schema:\n{json.dumps(updated_schema, indent=2)}",
        })

        # Log the LLM call if logger is provided
        if llm_logger:
            async with llm_logger.log_call(
                call_type="agent_attribute_update",
                prompt=prompt,
                retry_count=0,
                is_update=True,
                existing_agent_id=getattr(existing_agent, 'id', None),
                openai_model="gpt-4.1-nano",
                openai_messages=messages,
            ) as call_log:
                call_start_time = time.time()
                
                # Make OpenAI API call
                response = client.chat.completions.create(
                    model="gpt-4.1-nano",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=2000,
                )

                # Extract generated content
                ai_response_content = response.choices[0].message.content.strip()
                
                try:
                    # Parse AI response
                    ai_updated_schema = json.loads(ai_response_content)
                    
                    # Safely merge only text attributes, preserving skills and other configs
                    for attr in ["name", "purpose", "personality", "principles"]:
                        if attr in ai_updated_schema:
                            updated_schema[attr] = ai_updated_schema[attr]
                    
                    generated_content = {
                        "updated_attributes": {
                            attr: ai_updated_schema.get(attr) 
                            for attr in ["name", "purpose", "personality", "principles"]
                            if attr in ai_updated_schema
                        }
                    }
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse AI response as JSON: {e}")
                    generated_content = {"error": "Failed to parse AI response"}

                # Log successful call
                await llm_logger.log_successful_call(
                    call_log=call_log,
                    response=response,
                    generated_content=generated_content,
                    openai_messages=messages,
                    call_start_time=call_start_time,
                )

                # Extract token usage for return
                total_token_usage = extract_token_usage(response)
        else:
            # Make call without logging (fallback)
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
            )

            ai_response_content = response.choices[0].message.content.strip()
            
            try:
                ai_updated_schema = json.loads(ai_response_content)
                for attr in ["name", "purpose", "personality", "principles"]:
                    if attr in ai_updated_schema:
                        updated_schema[attr] = ai_updated_schema[attr]
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse AI response as JSON: {e}")

            total_token_usage = extract_token_usage(response)

    logger.info("Agent enhancement completed with minimal changes")
    return updated_schema, identified_skill_names, total_token_usage


async def generate_agent_attributes(
    prompt: str, 
    skills_config: Dict[str, Any], 
    client: OpenAI,
    llm_logger: Optional["LLMLogger"] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Generate agent attributes (name, purpose, personality, principles) from prompt.

    Args:
        prompt: The natural language prompt
        skills_config: Configuration of identified skills
        client: OpenAI client for API calls
        llm_logger: Optional LLM logger for tracking API calls

    Returns:
        A tuple of (agent_attributes, token_usage)
    """
    logger.info("Generating agent attributes from prompt")

    # Create skill summary for context
    skill_names = list(skills_config.keys())
    skill_summary = ", ".join(skill_names) if skill_names else "no specific skills"

    # Get conversation history if logger has a project_id
    history_messages = []
    if llm_logger:
        try:
            history_messages = await get_conversation_history(
                project_id=llm_logger.request_id,
                user_id=llm_logger.user_id,
            )
        except Exception as e:
            logger.warning(f"Failed to get conversation history: {e}")
            history_messages = []

    # Prepare messages for agent generation
    system_message = {
        "role": "system",
        "content": f"""You are generating agent attributes for an IntentKit AI agent.

Based on the user's description, create appropriate attributes for an agent that will use these skills: {skill_summary}

Generate a JSON object with these exact fields:
- "name": A clear, descriptive name for the agent (2-4 words)
- "purpose": A concise description of what the agent does (1-2 sentences)
- "personality": The agent's communication style and personality traits (1-2 sentences)
- "principles": Core rules and guidelines the agent follows (1-3 bullet points)

Make the attributes coherent and well-suited for the identified skills.
Return only valid JSON, no additional text.

If this is part of an ongoing conversation, consider the previous context while creating the agent.""",
    }

    # Build messages with conversation history
    messages = [system_message]
    
    # Add conversation history if available
    if history_messages:
        logger.info(f"Using {len(history_messages)} messages from conversation history")
        messages.extend(history_messages)
    
    # Add current user message
    messages.append({
        "role": "user",
        "content": f"Create an agent for: {prompt}",
    })

    # Log the LLM call if logger is provided
    if llm_logger:
        async with llm_logger.log_call(
            call_type="agent_attribute_generation",
            prompt=prompt,
            retry_count=0,
            is_update=False,
            openai_model="gpt-4.1-nano",
            openai_messages=messages,
        ) as call_log:
            call_start_time = time.time()
            
            # Make OpenAI API call
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
            )

            # Extract and parse generated content
            ai_response_content = response.choices[0].message.content.strip()
            
            try:
                attributes = json.loads(ai_response_content)
                generated_content = {"attributes": attributes}
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse agent attributes JSON: {e}")
                # Provide fallback attributes
                attributes = {
                    "name": "AI Assistant",
                    "purpose": "A helpful AI agent designed to assist users with various tasks.",
                    "personality": "Friendly, professional, and helpful. Always strives to provide accurate and useful information.",
                    "principles": "• Be helpful and accurate\n• Respect user privacy\n• Provide clear explanations",
                }
                generated_content = {"error": "Failed to parse AI response", "fallback_used": True, "attributes": attributes}

            # Log successful call
            await llm_logger.log_successful_call(
                call_log=call_log,
                response=response,
                generated_content=generated_content,
                openai_messages=messages,
                call_start_time=call_start_time,
            )

            # Extract token usage
            token_usage = extract_token_usage(response)
    else:
        # Make call without logging (fallback)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=messages,
            temperature=0.7,
            max_tokens=1500,
        )

        ai_response_content = response.choices[0].message.content.strip()
        
        try:
            attributes = json.loads(ai_response_content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent attributes JSON: {e}")
            attributes = {
                "name": "AI Assistant",
                "purpose": "A helpful AI agent designed to assist users with various tasks.",
                "personality": "Friendly, professional, and helpful. Always strives to provide accurate and useful information.",
                "principles": "• Be helpful and accurate\n• Respect user privacy\n• Provide clear explanations",
            }

        token_usage = extract_token_usage(response)

    logger.info(f"Generated agent attributes: {attributes.get('name', 'Unknown')}")
    return attributes, token_usage


async def generate_validated_agent(
    prompt: str,
    user_id: Optional[str] = None,
    existing_agent: Optional["AgentUpdate"] = None,
    llm_logger: Optional["LLMLogger"] = None,
    max_attempts: int = 3,
) -> Tuple[Dict[str, Any], Set[str], str]:
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
        llm_logger: Optional LLM logger for tracking API calls
        max_attempts: Maximum number of generation attempts

    Returns:
        A tuple of (validated_schema, identified_skills, summary_message)
    """
    start_time = time.time()

    # Create generation log (keeping existing aggregate logging for backward compatibility)
    async with get_session() as session:
        log_data = AgentGenerationLogCreate(
            user_id=user_id,
            prompt=prompt,
            existing_agent_id=getattr(existing_agent, 'id', None),
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
                        llm_logger=llm_logger,
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
                        llm_logger=llm_logger,
                        retry_count=attempt,
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

                    # Generate summary message
                    summary = await generate_agent_summary(
                        schema=schema,
                        identified_skills=identified_skills,
                        client=client,
                        llm_logger=llm_logger,
                    )

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
                            generation_time_ms=int((time.time() - start_time) * 1000),
                            retry_count=attempt,
                            success=True,
                        )

                    return schema, identified_skills, summary

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
                validation_errors={"errors": [str(e)]},
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
    llm_logger: Optional["LLMLogger"] = None,
    retry_count: int = 1,
) -> Tuple[Dict[str, Any], Set[str], Dict[str, Any]]:
    """Fix agent schema using AI based on validation errors.

    Args:
        original_prompt: The original user prompt
        failed_schema: The schema that failed validation
        validation_errors: List of validation error messages
        client: OpenAI client for API calls
        user_id: Optional user ID for validation
        existing_agent: Optional existing agent context
        llm_logger: Optional LLM logger for tracking API calls
        retry_count: Current retry attempt number

    Returns:
        A tuple of (fixed_schema, identified_skills, token_usage)
    """
    logger.info(f"Attempting to fix schema using AI (retry {retry_count})")

    # Prepare detailed error context for AI
    error_details = "\n".join([f"- {error}" for error in validation_errors])

    # Prepare messages for schema fixing
    messages = [
        {
            "role": "system",
            "content": """You are an expert at fixing IntentKit agent schema validation errors.

The user created an agent but the schema has validation errors. Your job is to fix these errors while preserving the user's intent.

CRITICAL RULES:
1. Only use real IntentKit skills that actually exist
2. Skills must have real states (not made-up ones)
3. Fix validation errors while maintaining user intent
4. Return only valid JSON for the complete agent schema
5. Do not add fake skills or fake states
6. ALWAYS preserve the owner field if it exists in the original schema

Common validation errors and fixes:
- Missing required fields: Add them with appropriate values
- Invalid skill names: Remove or replace with real skills
- Invalid skill states: Replace with real states for that skill
- Invalid model names: Use gpt-4.1-nano as default
- Missing skill configurations: Add proper enabled/states/api_key_provider structure
- Missing owner field: Will be automatically added after your response""",
        },
        {
            "role": "user",
            "content": f"""Original user request: {original_prompt}

Failed schema:
{json.dumps(failed_schema, indent=2)}

Validation errors to fix:
{error_details}

Please fix these errors and return the corrected agent schema as valid JSON.""",
        },
    ]

    # Log the LLM call if logger is provided
    if llm_logger:
        async with llm_logger.log_call(
            call_type="schema_error_correction",
            prompt=original_prompt,
            retry_count=retry_count,
            is_update=existing_agent is not None,
            existing_agent_id=getattr(existing_agent, 'id', None),
            openai_model="gpt-4.1-nano",
            openai_messages=messages,
        ) as call_log:
            call_start_time = time.time()
            
            # Make OpenAI API call
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=messages,
                temperature=0.3,
                max_tokens=3000,
            )

            # Extract and parse generated content
            ai_response_content = response.choices[0].message.content.strip()
            
            try:
                # Parse the fixed schema
                fixed_schema = json.loads(ai_response_content)
                
                # Ensure owner is set if user_id is provided
                if user_id:
                    fixed_schema["owner"] = user_id
                
                # Extract skills for return value
                identified_skills = set(fixed_schema.get("skills", {}).keys())
                
                generated_content = {
                    "fixed_schema": fixed_schema,
                    "validation_errors_addressed": validation_errors,
                    "identified_skills": list(identified_skills),
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI-fixed schema JSON: {e}")
                # Return original schema if AI response is invalid
                fixed_schema = failed_schema
                # Ensure owner is set even for fallback schema
                if user_id:
                    fixed_schema["owner"] = user_id
                identified_skills = set(failed_schema.get("skills", {}).keys())
                generated_content = {
                    "error": "Failed to parse AI response", 
                    "raw_response": ai_response_content,
                    "fallback_schema": fixed_schema,
                }

            # Log successful call
            await llm_logger.log_successful_call(
                call_log=call_log,
                response=response,
                generated_content=generated_content,
                openai_messages=messages,
                call_start_time=call_start_time,
            )

            # Extract token usage
            token_usage = extract_token_usage(response)
    else:
        # Make call without logging (fallback)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=messages,
            temperature=0.3,
            max_tokens=3000,
        )

        ai_response_content = response.choices[0].message.content.strip()
        
        try:
            fixed_schema = json.loads(ai_response_content)
            # Ensure owner is set if user_id is provided
            if user_id:
                fixed_schema["owner"] = user_id
            identified_skills = set(fixed_schema.get("skills", {}).keys())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI-fixed schema JSON: {e}")
            fixed_schema = failed_schema
            # Ensure owner is set even for fallback schema
            if user_id:
                fixed_schema["owner"] = user_id
            identified_skills = set(failed_schema.get("skills", {}).keys())

        token_usage = extract_token_usage(response)

    logger.info(f"AI schema correction completed (retry {retry_count})")
    return fixed_schema, identified_skills, token_usage
