"""Validation Module.

This module handles all validation operations for agent generation including:
- Schema validation against JSON schemas
- Agent-specific business logic validation
- Error formatting and handling
"""

import logging
import re
from typing import Any, Dict, List

import jsonschema
from pydantic import BaseModel, Field, ValidationError

from intentkit.config.config import config
from intentkit.models.agent import Agent, AgentUpdate

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Result of schema validation."""

    valid: bool = Field(..., description="Whether the schema is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")


async def validate_schema_against_json_schema(
    data: Dict[str, Any], json_schema: Dict[str, Any]
) -> ValidationResult:
    """Validate a schema against a JSON schema.

    Args:
        data: The schema to validate
        json_schema: The JSON schema to validate against

    Returns:
        ValidationResult with validation status and errors
    """
    result = ValidationResult(valid=True)

    try:
        jsonschema.validate(data, json_schema)
    except jsonschema.exceptions.ValidationError as e:
        result.valid = False
        result.errors.append(_format_validation_error(e))
    except Exception as e:
        result.valid = False
        result.errors.append(f"Schema validation failed: {str(e)}")

    return result


async def validate_schema(data: Dict[str, Any]) -> ValidationResult:
    """Validate a schema against the agent schema.

    Args:
        data: The schema to validate

    Returns:
        ValidationResult with validation status and errors
    """
    # Use the shared schema function with admin configuration
    schema = await Agent.get_json_schema(
        filter_owner_api_skills=True,
        admin_llm_skill_control=config.admin_llm_skill_control,
    )
    return await validate_schema_against_json_schema(data, schema)


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
    agent_data: Dict[str, Any], user_id: str = None
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
    if "model" not in fixed_schema or not fixed_schema["model"]:
        fixed_schema["model"] = (
            "gpt-4.1-nano"  # Use default model, let schema validation handle validity
        )
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
