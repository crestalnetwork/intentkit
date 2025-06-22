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
from .conversation_service import (
    ConversationService,
    get_conversation_history,
    get_project_metadata,
    get_projects_by_user,
)
from .llm_logger import (
    LLMLogger,
    create_llm_logger,
)
from .skill_processor import (
    filter_skills_for_auto_generation,
    identify_skills,
)
from .utils import (
    ALLOWED_MODELS,
    extract_token_usage,
    generate_agent_summary,
    generate_request_id,
)
from .validation import (
    ValidationResult,
    validate_agent_create,
    validate_schema,
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
    # Conversation history
    "ConversationService",
    "get_conversation_history",
    "get_project_metadata",
    "get_projects_by_user",
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
