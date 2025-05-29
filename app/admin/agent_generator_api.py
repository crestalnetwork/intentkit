"""Agent Generator API.

FastAPI endpoints for generating agent schemas from natural language prompts.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator

from app.admin.generator import generate_validated_agent_schema
from models.agent import AgentUpdate

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)


class AgentGenerateRequest(BaseModel):
    """Request model for agent generation."""

    prompt: str = Field(
        ...,
        description="Natural language description of the agent's desired capabilities",
        min_length=10,
        max_length=1000,
    )

    existing_agent: Optional[AgentUpdate] = Field(
        None,
        description="Existing agent to update. If provided, the LLM will make minimal changes to this agent based on the prompt. If null, a new agent will be created.",
    )

    user_id: Optional[str] = Field(
        None, description="User ID for logging and rate limiting purposes"
    )

    @validator("prompt")
    def validate_prompt_length(cls, v):
        if len(v) < 10:
            raise ValueError(
                "Prompt is too short. Please provide at least 10 characters describing the agent's capabilities."
            )
        if len(v) > 1000:
            raise ValueError(
                "Prompt is too long. Please keep your description under 1000 characters to ensure efficient processing."
            )
        return v


@router.post(
    "/generate",
    summary="Generate Agent from Natural Language Prompt",
)
async def generate_agent(
    request: AgentGenerateRequest,
) -> Dict[str, Any]:
    """Generate an agent schema from a natural language prompt.

    Converts plain English descriptions into complete, validated agent configurations.
    Automatically identifies required skills, sets up configurations, and ensures
    everything works correctly with intelligent error correction.

    **Request Body:**
    * `prompt` - Natural language description of the agent's desired capabilities
    * `existing_agent` - Optional existing agent to update (preserves current setup while adding capabilities)
    * `user_id` - Optional user ID for logging and rate limiting

    **Returns:**
    * `Dict[str, Any]` - Complete, validated agent schema ready for immediate use

    **Raises:**
    * `HTTPException`:
        - 400: Invalid prompt format or length
        - 500: Agent generation failed after retries
    """
    logger.info(f"Agent generation request received: {request.prompt[:100]}...")

    # Determine if this is an update operation
    is_update = request.existing_agent is not None

    if is_update:
        logger.info("Processing agent update with existing agent data")

    try:
        # Generate agent schema with automatic validation and AI self-correction
        agent_schema, identified_skills = await generate_validated_agent_schema(
            prompt=request.prompt,
            user_id=request.user_id,
            existing_agent=request.existing_agent,
        )

        logger.info("Agent generation completed successfully")
        if is_update:
            logger.info(
                "Agent schema updated via minimal changes with AI self-correction"
            )
        else:
            logger.info("New agent schema generated successfully with validation")

        return agent_schema

    except Exception as e:
        # All internal retries and AI self-correction failed
        logger.error(
            f"Agent generation failed after all attempts: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AgentGenerationFailed",
                "msg": f"Failed to generate valid agent: {str(e)}",
            },
        )
