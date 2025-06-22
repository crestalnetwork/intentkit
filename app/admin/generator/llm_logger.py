"""LLM Call Logger Module.

Tracks LLM API calls for cost analysis and debugging.
For conversation history, use conversation_service.py instead.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from .utils import generate_request_id

logger = logging.getLogger(__name__)


class LLMLogger:
    """Logger for tracking LLM API calls and costs."""

    def __init__(self, request_id: str, user_id: Optional[str] = None):
        """Initialize the LLM logger.

        Args:
            request_id: Unique request ID that groups related LLM calls
            user_id: Optional user ID for the request
        """
        self.request_id = request_id
        self.user_id = user_id

    @asynccontextmanager
    async def log_call(
        self,
        call_type: str,
        prompt: str,
        retry_count: int = 0,
        is_update: bool = False,
        existing_agent_id: Optional[str] = None,
        llm_model: Optional[str] = None,
        openai_messages: Optional[List[Dict[str, Any]]] = None,
    ):
        """Context manager for logging an LLM call.

        Args:
            call_type: Type of LLM call (e.g., 'agent_generation')
            prompt: The original prompt for this generation request
            retry_count: Retry attempt number (0 for initial, 1+ for retries)
            is_update: Whether this is an update operation
            existing_agent_id: ID of existing agent if update
            llm_model: LLM model being used
            openai_messages: Messages being sent to OpenAI

        Yields:
            Simple dict for tracking this call
        """
        call_info = {
            "type": call_type,
            "prompt": prompt,
            "request_id": self.request_id,
            "retry_count": retry_count,
        }

        logger.info(
            f"Started LLM call: {call_type} (request_id={self.request_id}, retry={retry_count})"
        )

        try:
            yield call_info
        except Exception as e:
            logger.error(
                f"LLM call failed: {call_type} (request_id={self.request_id}): {str(e)}"
            )
            raise

    async def log_successful_call(
        self,
        call_log: Dict[str, Any],
        response: Any,
        generated_content: Optional[Dict[str, Any]] = None,
        openai_messages: Optional[List[Dict[str, Any]]] = None,
        call_start_time: Optional[float] = None,
    ):
        """Log a successful LLM call completion.

        Args:
            call_log: The call log dict to update
            response: OpenAI API response
            generated_content: The generated content from the call
            openai_messages: Messages sent to OpenAI
            call_start_time: When the call started (for duration calculation)
        """
        logger.info(
            f"LLM call completed successfully: {call_log.get('type', 'unknown')}"
        )

        # Note: Conversation history is now handled by ConversationService
        # This logger now only tracks LLM call metrics and costs


def create_llm_logger(user_id: Optional[str] = None) -> LLMLogger:
    """Create a new LLM logger with a unique request ID.

    Args:
        user_id: Optional user ID for the request

    Returns:
        LLMLogger instance with unique request ID
    """
    request_id = generate_request_id()
    return LLMLogger(request_id=request_id, user_id=user_id)
