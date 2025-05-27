"""Agent Generator API Router.

This module provides API endpoints for generating agent schemas from natural language prompts.
"""

import logging
from typing import Any, Dict, Optional, List, Literal

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field, validator

from app.services.agent_generator.generator import (
    generate_agent_schema,
    create_agent_from_schema,
    update_agent_from_schema,
)
from utils.middleware import create_jwt_middleware
from app.config.config import config

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/v1/agent",
    tags=["Agent Generator"],
)

# Create JWT middleware
verify_jwt = create_jwt_middleware(config.admin_auth_enabled, config.admin_jwt_secret)

# List of allowed models
ALLOWED_MODELS = [
    "gpt-4o-mini", 
    "gpt-4.1-nano", 
    "gpt-4.1-mini"
]


class SkillState(BaseModel):
    """Model for skill state details."""
    
    name: str = Field(..., description="State name")
    description: str = Field(..., description="State description")
    access: Literal["public", "private"] = Field(..., description="Access level")


class SkillDetail(BaseModel):
    """Model for skill details."""
    
    name: str = Field(..., description="Skill name")
    description: str = Field(..., description="Skill description")
    states: List[SkillState] = Field(..., description="Available states")


class AgentGenerateRequest(BaseModel):
    """Request model for agent generation."""
    
    prompt: str = Field(
        ...,
        description="Natural language description of the agent's desired capabilities",
        min_length=10,
        max_length=1000
    )
    
    update_agent: bool = Field(
        False,
        description="Whether to create/update the agent in the system"
    )
    
    agent_id: Optional[str] = Field(
        None,
        description="ID of the agent to update (if null and update_agent is true, a new agent will be created)"
    )
    
    model_override: Optional[str] = Field(
        None,
        description="Override the default model selection"
    )
    
    temperature_override: Optional[float] = Field(
        None,
        description="Override the default temperature setting",
        ge=0.0,
        le=2.0
    )
    
    @validator("model_override")
    def validate_model(cls, v):
        if v is not None and v not in ALLOWED_MODELS:
            raise ValueError(f"Invalid model: {v}. Allowed models: {', '.join(ALLOWED_MODELS)}")
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
    agent_id: Optional[str] = Field(None, description="The ID of the created or updated agent")
    identified_skills: Optional[List[str]] = Field(None, description="List of skill names identified in the prompt")
    error: Optional[str] = Field(None, description="Error message if the request failed")


async def get_current_user_id(request: Request, credentials = Depends(verify_jwt)) -> str:
    """Get the current user ID from the JWT token.
    
    Args:
        request: The current request
        credentials: JWT credentials from verify_jwt dependency
        
    Returns:
        The user ID from the JWT token, or an empty string for unauthenticated requests
    """
    return credentials


@router.post("/generate", response_model=AgentGenerateResponse, summary="Generate Agent from Natural Language Prompt")
async def generate_agent(
    request: AgentGenerateRequest,
    background_tasks: BackgroundTasks,
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
    
    Args:
        request: The agent generation request
        background_tasks: FastAPI background tasks
        user_id: The ID of the current user
        
    Returns:
        AgentGenerateResponse with the generated schema and other information
    """
    try:
        # Log the request
        logger.info(f"Agent generation request received: {request.prompt[:100]}...")
        
        # Generate agent schema
        agent_schema = await generate_agent_schema(
            prompt=request.prompt,
            model_override=request.model_override,
            temperature_override=request.temperature_override
        )
        
        # Set owner to current user
        agent_schema["owner"] = user_id
        
        # Set temperature if provided
        if request.temperature_override is not None:
            agent_schema["temperature"] = request.temperature_override
        
        # Extract skill names for response
        identified_skills = list(agent_schema.get("skills", {}).keys())
        
        # Create or update agent if requested
        agent_id = request.agent_id
        if request.update_agent:
            if agent_id:
                # Update existing agent
                try:
                    await update_agent_from_schema(agent_id, agent_schema)
                    logger.info(f"Agent updated: {agent_id}")
                except Exception as e:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Failed to update agent: {str(e)}"
                    )
            else:
                # Create new agent
                try:
                    # Create agent
                    agent_id = await create_agent_from_schema(agent_schema)
                    logger.info(f"Agent created: {agent_id}")
                except Exception as e:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Failed to create agent: {str(e)}"
                    )
        
        # Return response
        return AgentGenerateResponse(
            success=True,
            agent_schema=agent_schema,
            agent_id=agent_id,
            identified_skills=identified_skills
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except ValueError as e:
        # Handle validation errors
        logger.error(f"Validation error: {str(e)}")
        return AgentGenerateResponse(
            success=False,
            agent_schema={},
            error=str(e)
        )
        
    except Exception as e:
        # Log the error
        logger.error(f"Agent generation failed: {str(e)}", exc_info=True)
        
        # Return error response
        return AgentGenerateResponse(
            success=False,
            agent_schema={},
            error=f"Agent generation failed: {str(e)}"
        ) 