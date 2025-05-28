"""Agent Generator API Router.

This module provides API endpoints for generating agent schemas from natural language prompts.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, ValidationError, validator

from app.admin.agent_generator import (
    ALLOWED_MODELS,
    create_agent_from_schema,
    generate_agent_schema,
    get_existing_agent_schema,
    update_agent_from_schema,
    validate_agent_create,
    validate_schema,
)
from app.config.config import config
from utils.middleware import create_jwt_middleware

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/v1/agent",
    tags=["Agent Generator"],
)

# Create JWT middleware
verify_jwt = create_jwt_middleware(config.admin_auth_enabled, config.admin_jwt_secret)


async def get_current_user_id(request: Request, credentials=Depends(verify_jwt)) -> str:
    """Get the current user ID from the JWT token.

    Args:
        request: The current request
        credentials: JWT credentials from verify_jwt dependency

    Returns:
        The user ID from the JWT token, or an empty string for unauthenticated requests
    """
    return credentials


class AgentGenerateRequest(BaseModel):
    """Request model for agent generation."""

    prompt: str = Field(
        ...,
        description="Natural language description of the agent's desired capabilities",
        min_length=10,
        max_length=1000,
    )

    update_agent: bool = Field(
        False, description="Whether to create/update the agent in the system"
    )

    agent_id: Optional[str] = Field(
        None,
        description="ID of the agent to update (if null and update_agent is true, a new agent will be created)",
    )

    model_override: Optional[str] = Field(
        None, description="Override the default model selection"
    )

    temperature_override: Optional[float] = Field(
        None, description="Override the default temperature setting", ge=0.0, le=2.0
    )

    @validator("model_override")
    def validate_model(cls, v):
        if v is not None and v not in ALLOWED_MODELS:
            raise ValueError(
                f"Invalid model: {v}. Allowed models: {', '.join(ALLOWED_MODELS)}"
            )
        return v

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

    @validator("agent_id")
    def validate_agent_id(cls, v, values):
        if v is not None and not values.get("update_agent", False):
            raise ValueError("agent_id can only be provided when update_agent is true")
        return v


class AgentGenerateResponse(BaseModel):
    """Response model for agent generation."""

    success: bool = Field(..., description="Whether the request was successful")
    agent_schema: Dict[str, Any] = Field(..., description="The generated agent schema")
    agent_id: Optional[str] = Field(
        None, description="The ID of the created or updated agent"
    )
    identified_skills: Optional[List[str]] = Field(
        None, description="List of skill names identified in the prompt"
    )
    error: Optional[str] = Field(
        None, description="Error message if the request failed"
    )
    schema_validation: Dict[str, Any] = Field(
        default_factory=dict, description="Results of schema validation"
    )


class AgentValidateResponse(BaseModel):
    """Response model for agent validation."""

    agent_id: str = Field(..., description="The ID of the validated agent")
    schema_valid: bool = Field(..., description="Whether the schema is valid")
    schema_errors: List[str] = Field(
        default_factory=list, description="Schema validation errors"
    )
    agent_valid: bool = Field(
        ..., description="Whether the agent passes business logic validation"
    )
    agent_errors: List[str] = Field(
        default_factory=list, description="Agent validation errors"
    )

    # Add summary fields for better readability
    overall_valid: bool = Field(
        ..., description="Whether the agent is completely valid"
    )
    error_count: int = Field(..., description="Total number of validation errors")
    summary: str = Field(..., description="Human-readable validation summary")

    def __init__(self, **data):
        # Calculate derived fields
        schema_errors = data.get("schema_errors", [])
        agent_errors = data.get("agent_errors", [])
        schema_valid = data.get("schema_valid", True)
        agent_valid = data.get("agent_valid", True)

        data["overall_valid"] = schema_valid and agent_valid
        data["error_count"] = len(schema_errors) + len(agent_errors)

        # Create summary
        if data["overall_valid"]:
            data["summary"] = "✅ Agent validation passed - no issues found"
        else:
            error_types = []
            if not schema_valid:
                error_types.append(f"{len(schema_errors)} schema error(s)")
            if not agent_valid:
                error_types.append(f"{len(agent_errors)} business logic error(s)")
            data["summary"] = f"❌ Agent validation failed - {', '.join(error_types)}"

        super().__init__(**data)


@router.post(
    "/generate",
    response_model=AgentGenerateResponse,
    summary="Generate Agent from Natural Language Prompt",
)
async def generate_agent(
    request: AgentGenerateRequest,
    user_id: str = Depends(get_current_user_id),
) -> AgentGenerateResponse:
    """Generate an agent schema based on a natural language prompt.

    This endpoint analyzes a natural language prompt to identify required skills and generates
    a complete, valid agent schema. Optionally, it can create a new agent or update an existing
    one with the generated schema.

    Examples:
    - "Create an agent that can search the web and post tweets about cryptocurrency prices"
    - "Make me a portfolio tracker that can check crypto prices and analyze my investments"
    - "Build a research assistant that can search the web and generate images"
    """
    try:
        logger.info(f"Agent generation request received: {request.prompt[:100]}...")

        # Validate existing agent if updating
        agent_id = request.agent_id
        if request.update_agent and agent_id:
            try:
                await get_existing_agent_schema(agent_id)
                logger.info(f"Retrieved existing agent schema for {agent_id}")
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))

        # Generate agent schema
        agent_schema, identified_skills = await generate_agent_schema(
            prompt=request.prompt,
            model_override=request.model_override,
            temperature_override=request.temperature_override,
            user_id=user_id,
        )

        # Validate the schema
        schema_validation = await validate_schema(agent_schema)
        agent_validation = await validate_agent_create(agent_schema, user_id)

        validation_result = {
            "schema_valid": schema_validation.valid,
            "schema_errors": schema_validation.errors,
            "agent_valid": agent_validation.valid,
            "agent_errors": agent_validation.errors,
        }

        # Create or update agent if requested and validation passed
        if request.update_agent and schema_validation.valid and agent_validation.valid:
            if agent_id:
                try:
                    await update_agent_from_schema(agent_id, agent_schema)
                    logger.info(f"Agent updated: {agent_id}")
                except Exception as e:
                    raise HTTPException(
                        status_code=404, detail=f"Failed to update agent: {str(e)}"
                    )
            else:
                try:
                    agent_id = await create_agent_from_schema(agent_schema)
                    logger.info(f"Agent created: {agent_id}")
                except Exception as e:
                    raise HTTPException(
                        status_code=422, detail=f"Failed to create agent: {str(e)}"
                    )

        return AgentGenerateResponse(
            success=True,
            agent_schema=agent_schema,
            agent_id=agent_id,
            identified_skills=list(identified_skills),
            schema_validation=validation_result,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return AgentGenerateResponse(
            success=False,
            agent_schema={},
            error=str(e),
            schema_validation={"schema_valid": False, "agent_valid": False},
        )
    except Exception as e:
        logger.error(f"Agent generation failed: {str(e)}", exc_info=True)
        return AgentGenerateResponse(
            success=False,
            agent_schema={},
            error=f"Agent generation failed: {str(e)}",
            schema_validation={"schema_valid": False, "agent_valid": False},
        )


@router.get(
    "/validate",
    response_model=AgentValidateResponse,
    summary="Validate Agent Schema",
)
async def validate_agent_schema(
    agent_id: str = Query(
        ...,
        description="The ID of the agent to validate",
        min_length=1,
        max_length=50,
        regex=r"^[a-z0-9-]+$",
    ),
    user_id: str = Depends(get_current_user_id),
) -> AgentValidateResponse:
    """Validate an existing agent schema.

    Args:
        agent_id: The ID of the agent to validate
        user_id: The ID of the current user

    Returns:
        AgentValidateResponse with validation results
    """
    try:
        # Get existing agent schema
        existing_schema = await get_existing_agent_schema(agent_id)

        # Validate the schema
        schema_validation = await validate_schema(existing_schema)
        agent_validation = await validate_agent_create(existing_schema, user_id)

        return AgentValidateResponse(
            agent_id=agent_id,
            schema_valid=schema_validation.valid,
            schema_errors=schema_validation.errors,
            agent_valid=agent_validation.valid,
            agent_errors=agent_validation.errors,
        )

    except ValueError as e:
        # Agent not found
        raise HTTPException(status_code=404, detail=f"Agent not found: {str(e)}")

    except ValidationError as e:
        # Pydantic validation errors
        logger.error(f"Validation error for agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=422, detail=f"Validation error: {str(e)}")

    except Exception as e:
        # Unexpected errors
        logger.error(f"Validation failed for agent {agent_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
