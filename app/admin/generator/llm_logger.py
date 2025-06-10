"""LLM Call Logger Module.

Simple conversation tracking for project-based agent generation.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from .utils import generate_request_id

logger = logging.getLogger(__name__)

# In-memory storage for conversation history
_conversation_history: Dict[str, List[Dict[str, str]]] = {}
_project_metadata: Dict[
    str, Dict[str, Any]
] = {}  # Store project metadata including user_id


class LLMLogger:
    """Simple logger for tracking conversation history per project."""

    def __init__(self, request_id: str, user_id: Optional[str] = None):
        """Initialize the LLM logger.

        Args:
            request_id: Unique request ID that groups related conversations
            user_id: Optional user ID for the request
        """
        self.request_id = request_id
        self.user_id = user_id

        # Store project metadata when logger is created
        if self.request_id not in _project_metadata:
            _project_metadata[self.request_id] = {
                "user_id": user_id,
                "created_at": time.time(),
                "last_activity": time.time(),
            }

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
        """Context manager for logging an LLM call (simplified for conversation tracking).

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

        # Store conversation in memory for this project
        if generated_content and self.request_id:
            self._store_conversation_turn(
                prompt=call_log.get("prompt", ""),
                response_content=generated_content,
                call_type=call_log.get("type", ""),
            )

    def _store_conversation_turn(
        self, prompt: str, response_content: Dict[str, Any], call_type: str
    ):
        """Store a conversation turn in memory."""
        if self.request_id not in _conversation_history:
            _conversation_history[self.request_id] = []

        # Add user message
        _conversation_history[self.request_id].append(
            {"role": "user", "content": prompt}
        )

        # Add AI response based on call type
        ai_content = self._format_ai_response(response_content, call_type)
        if ai_content:
            _conversation_history[self.request_id].append(
                {"role": "assistant", "content": ai_content}
            )

        # Update project metadata
        if self.request_id in _project_metadata:
            _project_metadata[self.request_id]["last_activity"] = time.time()

    def _format_ai_response(
        self, content: Dict[str, Any], call_type: str
    ) -> Optional[str]:
        """Format AI response content for conversation history."""
        if call_type == "agent_attribute_generation" and "attributes" in content:
            attrs = content["attributes"]
            response = "I've created an agent with the following attributes:\n"
            response += f"Name: {attrs.get('name', 'N/A')}\n"
            response += f"Purpose: {attrs.get('purpose', 'N/A')}\n"
            response += f"Personality: {attrs.get('personality', 'N/A')}\n"
            response += f"Principles: {attrs.get('principles', 'N/A')}"
            return response

        elif call_type == "agent_attribute_update" and "updated_attributes" in content:
            updates = content["updated_attributes"]
            response = "I've updated the agent with the following changes:\n"
            for attr, value in updates.items():
                if value:
                    response += f"{attr.title()}: {value}\n"
            return response

        elif call_type == "schema_error_correction":
            return "I've corrected the agent schema to fix validation errors."

        elif call_type == "tag_generation":
            if "selected_tags" in content:
                tags = content["selected_tags"]
                if tags:
                    return f"I've generated the following tags for this agent: {', '.join(tags)}"
                else:
                    return "I couldn't find appropriate tags for this agent from the available categories."
            else:
                return "I attempted to generate tags for the agent."

        return None


def create_llm_logger(user_id: Optional[str] = None) -> LLMLogger:
    """Create a new LLM logger with a unique request ID.

    Args:
        user_id: Optional user ID for the request

    Returns:
        LLMLogger instance with unique request ID
    """
    request_id = generate_request_id()
    return LLMLogger(request_id=request_id, user_id=user_id)


async def get_conversation_history(
    project_id: str,
    user_id: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Get conversation history for a project from memory.

    Args:
        project_id: Project/request ID to get history for
        user_id: Optional user ID for access validation

    Returns:
        List of conversation messages in chronological order

    Raises:
        ValueError: If project not found or access denied
    """
    logger.info(f"Getting conversation history for project: {project_id}")

    # Check if project exists
    if project_id not in _conversation_history:
        logger.warning(f"Project {project_id} not found in conversation history")
        return []

    # Check if project exists in metadata
    if project_id not in _project_metadata:
        logger.warning(f"Project {project_id} not found in project metadata")
        return []

    # Access control: if user_id is provided, verify it matches the project owner
    if user_id is not None:
        project_metadata = _project_metadata.get(project_id, {})
        project_user_id = project_metadata.get("user_id")

        if project_user_id and project_user_id != user_id:
            logger.warning(
                f"Access denied: user {user_id} cannot access project {project_id} owned by {project_user_id}"
            )
            raise ValueError(f"Access denied: cannot access project {project_id}")

    history = _conversation_history.get(project_id, [])
    logger.info(f"Found {len(history)} conversation messages for project {project_id}")

    return history


async def get_project_metadata(project_id: str) -> Optional[Dict[str, Any]]:
    """Get metadata for a specific project.

    Args:
        project_id: Project/request ID to get metadata for

    Returns:
        Project metadata dict or None if not found
    """
    return _project_metadata.get(project_id)


async def get_projects_by_user(
    user_id: Optional[str] = None, limit: int = 50
) -> List[Dict[str, Any]]:
    """Get recent projects with conversation history, optionally filtered by user.

    Args:
        user_id: Optional user ID to filter projects
        limit: Maximum number of projects to return

    Returns:
        List of project dictionaries with conversation history and metadata
    """
    logger.info(f"Getting projects for user_id={user_id}, limit={limit}")

    projects = []

    # Get all projects with their metadata and conversation history
    for project_id, metadata in _project_metadata.items():
        # Filter by user_id if provided
        if user_id and metadata.get("user_id") != user_id:
            continue

        # Get conversation history for this project
        conversation_history = _conversation_history.get(project_id, [])

        # Only include projects with conversation history
        if conversation_history:
            project_info = {
                "project_id": project_id,
                "user_id": metadata.get("user_id"),
                "created_at": metadata.get("created_at"),
                "last_activity": metadata.get("last_activity"),
                "message_count": len(conversation_history),
                "last_message": conversation_history[-1]
                if conversation_history
                else None,
                "first_message": conversation_history[0]
                if conversation_history
                else None,
                "conversation_history": conversation_history,
            }
            projects.append(project_info)

    # Sort by last activity (most recent first)
    projects.sort(key=lambda x: x.get("last_activity", 0), reverse=True)

    # Limit results
    projects = projects[:limit]

    logger.info(f"Retrieved {len(projects)} projects")
    return projects
