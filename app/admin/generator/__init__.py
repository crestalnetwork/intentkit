"""Agent Generator Package.

AI-powered system for generating IntentKit agent schemas from natural language prompts.
Each LLM call is individually tracked with request ID and retry count for cost analysis.
"""

from .agent_generator import (
    generate_agent_schema,
    generate_validated_agent_schema,
)
from .ai_assistant import (
    enhance_agent,
    generate_agent_attributes,
    generate_validated_agent,
)
from .llm_logger import (
    create_llm_logger,
    get_conversation_history,
    LLMLogger,
)
from .skill_processor import (
    filter_skills_for_auto_generation,
    identify_skills,
)
from .utils import extract_token_usage, generate_agent_summary, generate_request_id, ALLOWED_MODELS
from .validation import (
    validate_agent_create,
    validate_schema,
    ValidationResult,
)

__all__ = [
    # Main generation functions
    "generate_agent_schema",
    "generate_validated_agent_schema",
    "generate_validated_agent",
    # AI operations
    "enhance_agent",
    "generate_agent_attributes",
    "generate_agent_summary",
    "get_conversation_history",
    # LLM logging
    "create_llm_logger",
    "generate_request_id",
    "LLMLogger",
    # Skill processing
    "identify_skills",
    "filter_skills_for_auto_generation",
    # Utilities
    "extract_token_usage",
    "ALLOWED_MODELS",
    # Validation
    "validate_schema",
    "validate_agent_create",
    "ValidationResult",
]
