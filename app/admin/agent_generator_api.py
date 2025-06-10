"""Agent Generator API.

FastAPI endpoints for generating agent schemas from natural language prompts.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator

from app.admin.generator import generate_validated_agent_schema
from app.admin.generator.llm_logger import (
    LLMLogger,
    create_llm_logger,
    get_conversation_history,
    get_project_metadata,
    get_projects_by_user,
)
from app.admin.generator.utils import generate_tags_from_nation_api
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

    tags: List[Dict[str, int]] = Field(
        default_factory=list,
        description="Generated tags for the agent as ID objects: [{'id': 1}, {'id': 2}]",
    )


class GenerationsListRequest(BaseModel):
    """Request model for getting generations list."""

    user_id: Optional[str] = Field(None, description="User ID to filter generations")

    limit: int = Field(
        default=50,
        description="Maximum number of recent projects to return",
        ge=1,
        le=100,
    )


class GenerationsListResponse(BaseModel):
    """Response model for generations list."""

    projects: List[Dict[str, Any]] = Field(
        ..., description="List of recent projects with their conversation history"
    )


class GenerationDetailResponse(BaseModel):
    """Response model for single generation detail."""

    project_id: str = Field(..., description="Project ID")
    user_id: Optional[str] = Field(None, description="User ID who owns this project")
    created_at: Optional[str] = Field(None, description="Project creation timestamp")
    last_activity: Optional[str] = Field(None, description="Last activity timestamp")
    message_count: int = Field(..., description="Number of messages in conversation")
    last_message: Optional[Dict[str, Any]] = Field(
        None, description="Last message in conversation"
    )
    first_message: Optional[Dict[str, Any]] = Field(
        None, description="First message in conversation"
    )
    conversation_history: List[Dict[str, Any]] = Field(
        ..., description="Full conversation history"
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

        # Generate tags using Nation API
        tags = await generate_tags_from_nation_api(agent_schema, request.prompt)

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
            agent=agent_schema, project_id=project_id, summary=summary, tags=tags
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


@router.get(
    "/generations",
    summary="Get Generations List by User",
    response_model=GenerationsListResponse,
)
async def get_generations(
    user_id: Optional[str] = None, limit: int = 50
) -> GenerationsListResponse:
    """Get all projects/generations for a user.

    **Query Parameters:**
    * `user_id` - Optional user ID to filter projects
    * `limit` - Maximum number of recent projects to return (default: 50, max: 100)

    **Returns:**
    * `GenerationsListResponse` - Contains list of projects with their conversation history

    **Raises:**
    * `HTTPException`:
        - 400: Invalid parameters
        - 500: Failed to retrieve generations
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")

    logger.info(f"Getting generations for user_id={user_id}, limit={limit}")

    try:
        # Get recent projects with their conversation history
        projects = await get_projects_by_user(user_id=user_id, limit=limit)

        logger.info(f"Retrieved {len(projects)} projects for user {user_id}")
        return GenerationsListResponse(projects=projects)

    except Exception as e:
        logger.error(f"Failed to retrieve generations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GenerationsRetrievalFailed",
                "msg": f"Failed to retrieve generations: {str(e)}",
            },
        )


@router.get(
    "/generations/{project_id}",
    summary="Get Generation Detail by Project ID",
    response_model=GenerationDetailResponse,
)
async def get_generation_detail(
    project_id: str, user_id: Optional[str] = None
) -> GenerationDetailResponse:
    """Get specific project conversation history.

    **Path Parameters:**
    * `project_id` - Project ID to get conversation history for

    **Query Parameters:**
    * `user_id` - Optional user ID for access validation

    **Returns:**
    * `GenerationDetailResponse` - Contains full conversation history for the project

    **Raises:**
    * `HTTPException`:
        - 404: Project not found or access denied
        - 500: Failed to retrieve generation detail
    """
    logger.info(
        f"Getting generation detail for project_id={project_id}, user_id={user_id}"
    )

    try:
        # Get conversation history for the specific project
        try:
            conversation_history = await get_conversation_history(
                project_id=project_id,
                user_id=user_id,  # Used for additional access validation
            )
        except ValueError as ve:
            logger.warning(f"Access denied or project not found: {ve}")
            raise HTTPException(status_code=404, detail=str(ve))

        if not conversation_history:
            logger.warning(f"No conversation history found for project {project_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No conversation history found for project {project_id}",
            )

        # Get project metadata for additional information
        project_metadata = await get_project_metadata(project_id)

        logger.info(
            f"Retrieved conversation with {len(conversation_history)} messages for project {project_id}"
        )

        return GenerationDetailResponse(
            project_id=project_id,
            user_id=project_metadata.get("user_id") if project_metadata else user_id,
            created_at=datetime.fromtimestamp(
                project_metadata.get("created_at")
            ).isoformat()
            if project_metadata and project_metadata.get("created_at")
            else None,
            last_activity=datetime.fromtimestamp(
                project_metadata.get("last_activity")
            ).isoformat()
            if project_metadata and project_metadata.get("last_activity")
            else None,
            message_count=len(conversation_history),
            last_message=conversation_history[-1] if conversation_history else None,
            first_message=conversation_history[0] if conversation_history else None,
            conversation_history=conversation_history,
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve generation detail: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "GenerationDetailRetrievalFailed",
                "msg": f"Failed to retrieve generation detail: {str(e)}",
            },
        )
