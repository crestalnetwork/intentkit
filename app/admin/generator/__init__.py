"""Agent Generator Package.

This package contains all the modular components for AI-powered agent generation:
- agent_generator: Main orchestrator and entry points
- skill_processor: Skill identification, validation, and filtering
- validation: Schema and business logic validation
- ai_assistant: AI-powered operations and error correction
"""

from .agent_generator import (
    generate_agent_schema,
    generate_validated_agent_schema,
)
from .ai_assistant import (
    enhance_agent,
    fix_agent_schema_with_ai,
    generate_agent_attributes,
    generate_validated_agent,
)
from .skill_processor import (
    filter_skills_for_auto_generation,
    identify_skills,
    validate_skills_exist,
)
from .validation import (
    ValidationResult,
    validate_agent_create,
    validate_schema,
    validate_schema_against_json_schema,
)

__all__ = [
    # Main functions
    "generate_agent_schema",
    "generate_validated_agent_schema",
    # Skill processing
    "filter_skills_for_auto_generation",
    "identify_skills",
    "validate_skills_exist",
    # Validation
    "ValidationResult",
    "validate_agent_create",
    "validate_schema",
    "validate_schema_against_json_schema",
    # AI operations
    "enhance_agent",
    "generate_agent_attributes",
    "generate_validated_agent",
    "fix_agent_schema_with_ai",
]
