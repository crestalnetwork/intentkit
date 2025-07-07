import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.models.db import get_db
from intentkit.models.llm import LLMModelInfo, LLMModelInfoTable, LLMProvider

# Import functions from skill_processor
from app.admin.generator.skill_processor import (
    AVAILABLE_SKILL_CATEGORIES,
    get_skill_states,
    get_skill_keyword_config,
    get_skill_default_api_key_provider,
)

# Import additional modules for our custom schema loading

# Cache for skill schemas
_skill_schemas_cache: Dict[str, Dict[str, Any]] = {}


class SkillState(BaseModel):
    """Detailed skill state information."""
    
    name: str = Field(..., description="State name")
    title: Optional[str] = Field(None, description="Display title for the state")
    description: Optional[str] = Field(None, description="Description of what this state does")
    default_value: str = Field("disabled", description="Default value for this state")
    options: List[str] = Field(default_factory=list, description="Available options (disabled, public, private)")


class BasicSkill(BaseModel):
    """Basic skill information with comprehensive details."""
    
    skill_name: str = Field(..., description="The skill category name")
    title: Optional[str] = Field(None, description="Display title from schema")
    description: Optional[str] = Field(None, description="Description from schema")
    icon_url: Optional[str] = Field(None, description="URL to the skill icon")
    x_tags: List[str] = Field(default_factory=list, description="Tags/categories for the skill")
    states: List[SkillState] = Field(default_factory=list, description="Available skill states with details")
    simple_states: List[str] = Field(default_factory=list, description="Simple list of state names")
    api_key_provider_options: List[str] = Field(default_factory=list, description="Available API key provider options")
    default_api_key_provider: str = Field("platform", description="Default API key provider")
    requires_user_api_key: bool = Field(False, description="Whether user needs to provide their own API key")
    requires_agent_owner_api_key: bool = Field(False, description="Whether agent owner must provide API key")
    has_schema: bool = Field(True, description="Whether the skill has a schema file")
    keywords: List[str] = Field(default_factory=list, description="Keywords for skill discovery")


def load_skill_schema(skill_name: str) -> Optional[Dict[str, Any]]:
    """Load schema.json for a specific skill with correct path."""
    if skill_name in _skill_schemas_cache:
        return _skill_schemas_cache[skill_name]

    try:
        # Get the correct path to skills directory
        # From intentkit/app/admin/metadata.py, go to intentkit/intentkit/skills/
        current_file = Path(__file__)
        skills_dir = current_file.parent.parent.parent / "intentkit" / "skills"
        schema_path = skills_dir / skill_name / "schema.json"

        logging.debug(f"Looking for schema at: {schema_path}")

        if schema_path.exists():
            with open(schema_path, "r") as f:
                schema = json.load(f)
                _skill_schemas_cache[skill_name] = schema
                logging.debug(f"Successfully loaded schema for {skill_name}: title='{schema.get('title')}', description='{schema.get('description', '')[:50]}...'")
                return schema
        else:
            logging.warning(f"Schema file not found for skill: {skill_name} at {schema_path}")
            return None
    except Exception as e:
        logging.error(f"Error loading schema for skill {skill_name}: {e}")
        return None


def parse_skill_states_from_schema(schema: Dict[str, Any], actual_states: Set[str]) -> List[SkillState]:
    """Parse detailed state information from schema."""
    states = []
    
    if not schema or "properties" not in schema or "states" not in schema["properties"]:
        # Fallback to actual states without details
        return [SkillState(name=state, options=["disabled", "public", "private"]) for state in sorted(actual_states)]
    
    states_schema = schema["properties"]["states"]
    if "properties" not in states_schema:
        return [SkillState(name=state, options=["disabled", "public", "private"]) for state in sorted(actual_states)]
    
    for state_name, state_config in states_schema["properties"].items():
        if state_name in actual_states:
            title = state_config.get("title", state_name)
            description = state_config.get("description", "")
            default_value = state_config.get("default", "disabled")
            options = state_config.get("enum", ["disabled", "public", "private"])
            
            states.append(SkillState(
                name=state_name,
                title=title,
                description=description,
                default_value=default_value,
                options=options
            ))
    
    # Add any states that exist in actual_states but not in schema
    schema_state_names = set(states_schema["properties"].keys())
    missing_states = actual_states - schema_state_names
    for state_name in missing_states:
        states.append(SkillState(
            name=state_name,
            options=["disabled", "public", "private"]
        ))
    
    return sorted(states, key=lambda x: x.name)


def determine_api_key_requirements(schema: Optional[Dict[str, Any]], default_provider: str) -> tuple[bool, bool]:
    """Determine API key requirements based on schema and default provider."""
    requires_user_api_key = False
    requires_agent_owner_api_key = False
    
    if not schema or "properties" not in schema or "api_key_provider" not in schema["properties"]:
        return requires_user_api_key, requires_agent_owner_api_key
    
    api_key_provider = schema["properties"]["api_key_provider"]
    provider_options = api_key_provider.get("enum", [])
    
    # If agent_owner is the only option, then agent owner MUST provide API key
    if provider_options == ["agent_owner"]:
        requires_agent_owner_api_key = True
    # If default is agent_owner, then by default agent owner needs to provide
    elif default_provider == "agent_owner":
        requires_user_api_key = True  # User (agent owner) needs to provide
    # If both platform and agent_owner are available, user CAN provide their own
    elif "agent_owner" in provider_options and "platform" in provider_options:
        requires_user_api_key = False  # Optional - user can choose
    
    return requires_user_api_key, requires_agent_owner_api_key


# Create a readonly router for metadata endpoints
metadata_router_readonly = APIRouter(tags=["Metadata"])


class LLMModelInfoWithProviderName(LLMModelInfo):
    """LLM model information with provider display name."""

    provider_name: str


@metadata_router_readonly.get(
    "/metadata/skills",
    response_model=List[BasicSkill],
    summary="Get all skills",
    description="Returns a list of all available skills in the system",
)
async def get_skills():
    """
    Get all skills available in the system.

    **Returns:**
    * `List[BasicSkill]` - List of all skills
    """
    try:
        skills = []
        
        # Get keyword configuration for all skills
        keyword_config = get_skill_keyword_config()
        
        # Process each available skill category
        for skill_name in sorted(AVAILABLE_SKILL_CATEGORIES):
            try:
                # Load schema for this skill
                schema = load_skill_schema(skill_name)
                
                # Get skill states
                actual_states = get_skill_states(skill_name)
                
                # Get keywords for this skill
                keywords = keyword_config.get(skill_name, [skill_name])
                
                # Extract information from schema
                title = schema.get("title") if schema else None
                description = schema.get("description") if schema else None
                icon_url = schema.get("x-icon") if schema else None
                x_tags = schema.get("x-tags", []) if schema else []
                
                # Get API key provider information
                api_key_provider_options = []
                if schema and "properties" in schema and "api_key_provider" in schema["properties"]:
                    api_key_provider = schema["properties"]["api_key_provider"]
                    if "enum" in api_key_provider:
                        api_key_provider_options = api_key_provider["enum"]
                
                # Get default API key provider
                default_api_key_provider = get_skill_default_api_key_provider(skill_name)
                
                # Determine API key requirements
                requires_user_api_key, requires_agent_owner_api_key = determine_api_key_requirements(
                    schema, default_api_key_provider
                )
                
                # Parse detailed state information
                detailed_states = parse_skill_states_from_schema(schema, actual_states)
                simple_states = sorted(list(actual_states)) if actual_states else []
                
                # Create the basic skill object
                skill = BasicSkill(
                    skill_name=skill_name,
                    title=title,
                    description=description,
                    icon_url=icon_url,
                    x_tags=x_tags,
                    states=detailed_states,
                    simple_states=simple_states,
                    api_key_provider_options=api_key_provider_options,
                    default_api_key_provider=default_api_key_provider,
                    requires_user_api_key=requires_user_api_key,
                    requires_agent_owner_api_key=requires_agent_owner_api_key,
                    has_schema=schema is not None,
                    keywords=keywords,
                )
                
                skills.append(skill)
                
            except Exception as e:
                logging.warning(f"Error processing skill {skill_name}: {e}")
                # Create a minimal entry for skills that failed to process
                skill = BasicSkill(
                    skill_name=skill_name,
                    title=skill_name,
                    description=f"Skill {skill_name} (processing error)",
                    icon_url=None,
                    x_tags=[],
                    states=[],
                    simple_states=[],
                    api_key_provider_options=[],
                    default_api_key_provider="platform",
                    requires_user_api_key=False,
                    requires_agent_owner_api_key=False,
                    has_schema=False,
                    keywords=[skill_name],
                )
                skills.append(skill)
        
        logging.info(f"Successfully processed {len(skills)} skills")
        return skills
        
    except Exception as e:
        logging.error(f"Error getting skills: {e}")
        raise


@metadata_router_readonly.get(
    "/metadata/llms",
    response_model=List[LLMModelInfoWithProviderName],
    summary="Get all LLM models",
    description="Returns a list of all available LLM models in the system",
)
async def get_llms(db: AsyncSession = Depends(get_db)):
    """
    Get all LLM models available in the system.

    **Returns:**
    * `List[LLMModelInfoWithProviderName]` - List of all LLM models with provider display names
    """
    try:
        # Query all LLM models from the database
        stmt = select(LLMModelInfoTable)
        result = await db.execute(stmt)
        models = result.scalars().all()

        # Convert to LLMModelInfoWithProviderName models
        result_models = []
        for model in models:
            model_info = LLMModelInfo.model_validate(model)
            # Convert provider string to LLMProvider enum if needed
            provider = (
                LLMProvider(model_info.provider)
                if isinstance(model_info.provider, str)
                else model_info.provider
            )
            result_models.append(
                LLMModelInfoWithProviderName(
                    **model_info.model_dump(),
                    provider_name=provider.display_name(),
                )
            )
        return result_models
    except Exception as e:
        logging.error(f"Error getting LLM models: {e}")
        raise
