"""Agent Generator API.

FastAPI endpoints for generating agent schemas from natural language prompts.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator

from app.admin.generator import generate_validated_agent_schema
from app.admin.generator.llm_logger import LLMLogger, create_llm_logger
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

    project_id: Optional[str] = Field(
        None,
        description="Project ID for conversation history. If not provided, a new project will be created.",
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


class AgentGenerateResponse(BaseModel):
    """Response model for agent generation."""

    agent: Dict[str, Any] = Field(..., description="The generated agent schema")

    project_id: str = Field(..., description="Project ID for this conversation session")

    summary: str = Field(
        ..., description="Human-readable summary of the generated agent"
    )


@router.post(
    "/generate",
    summary="Generate Agent from Natural Language Prompt",
    response_model=AgentGenerateResponse,
)
async def generate_agent(
    request: AgentGenerateRequest,
) -> AgentGenerateResponse:
    """Generate an agent schema from a natural language prompt.

    Converts plain English descriptions into complete, validated agent configurations.
    Automatically identifies required skills, sets up configurations, and ensures
    everything works correctly with intelligent error correction.

    **Request Body:**
    * `prompt` - Natural language description of the agent's desired capabilities
    * `existing_agent` - Optional existing agent to update (preserves current setup while adding capabilities)
    * `user_id` - Optional user ID for logging and rate limiting
    * `project_id` - Optional project ID for conversation history

    **Returns:**
    * `AgentGenerateResponse` - Contains agent schema, project ID, and human-readable summary

    **Raises:**
    * `HTTPException`:
        - 400: Invalid prompt format or length
        - 500: Agent generation failed after retries
    """
    # Create or reuse LLM logger based on project_id
    if request.project_id:
        llm_logger = LLMLogger(request_id=request.project_id, user_id=request.user_id)
        project_id = request.project_id
        logger.info(f"Using existing project_id: {project_id}")
    else:
        llm_logger = create_llm_logger(user_id=request.user_id)
        project_id = llm_logger.request_id
        logger.info(f"Created new project_id: {project_id}")

    logger.info(
        f"Agent generation request received: {request.prompt[:100]}... "
        f"(project_id={project_id})"
    )

    # Determine if this is an update operation
    is_update = request.existing_agent is not None

    if is_update:
        logger.info(
            f"Processing agent update with existing agent data (project_id={project_id})"
        )

    try:
        # Generate agent schema with automatic validation and AI self-correction
        (
            agent_schema,
            identified_skills,
            summary,
        ) = await generate_validated_agent_schema(
            prompt=request.prompt,
            user_id=request.user_id,
            existing_agent=request.existing_agent,
            llm_logger=llm_logger,
        )

        logger.info(
            f"Agent generation completed successfully (project_id={project_id})"
        )
        if is_update:
            logger.info(
                f"Agent schema updated via minimal changes with AI self-correction (project_id={project_id})"
            )
        else:
            logger.info(
                f"New agent schema generated successfully with validation (project_id={project_id})"
            )

        return AgentGenerateResponse(
            agent=agent_schema, project_id=project_id, summary=summary
        )

    except Exception as e:
        # All internal retries and AI self-correction failed
        logger.error(
            f"Agent generation failed after all attempts (project_id={project_id}): {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AgentGenerationFailed",
                "msg": f"Failed to generate valid agent: {str(e)}",
                "project_id": project_id,
            },
        )
