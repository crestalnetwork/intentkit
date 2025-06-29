"""Conversation Service Module.

Handles conversation history storage and retrieval for agent generation.
This is separate from LLM logging which tracks technical API calls.
"""

import logging
from typing import Any, Dict, List, Optional

from intentkit.models.conversation import (
    ConversationMessage,
    ConversationMessageCreate,
    ConversationProject,
    ConversationProjectCreate,
)

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversation history."""

    def __init__(self, project_id: str, user_id: Optional[str] = None):
        """Initialize conversation service.

        Args:
            project_id: Unique identifier for the conversation project
            user_id: Optional user ID for access control
        """
        self.project_id = project_id
        self.user_id = user_id
        self._project: Optional[ConversationProject] = None

    async def _ensure_project(self) -> ConversationProject:
        """Ensure project exists and return it."""
        if not self._project:
            self._project = await create_or_get_project(self.project_id, self.user_id)
        return self._project

    async def add_user_message(
        self, content: str, message_metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationMessage:
        """Add a user message to the conversation."""
        return await add_message(
            self.project_id, "user", content, message_metadata, self.user_id
        )

    async def add_assistant_message(
        self, content: str, message_metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationMessage:
        """Add an assistant message to the conversation."""
        return await add_message(
            self.project_id, "assistant", content, message_metadata, self.user_id
        )

    async def get_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        try:
            return await get_conversation_history(self.project_id, self.user_id)
        except ValueError:
            return []

    async def get_recent_context(self, max_messages: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation context for the LLM."""
        history = await self.get_history()
        return history[-max_messages:] if history else []

    def format_ai_response(
        self, content: Dict[str, Any], call_type: str
    ) -> Optional[str]:
        """Format AI response content for conversation history.

        Args:
            content: Generated content from the AI call
            call_type: Type of AI operation

        Returns:
            Formatted response string or None if no response needed
        """
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


async def create_or_get_project(
    project_id: str, user_id: Optional[str] = None
) -> ConversationProject:
    """Create or get a conversation project."""
    # Try to get existing project first
    existing_project = await ConversationProject.get(project_id)
    if existing_project:
        return existing_project

    # Create new project
    project_create = ConversationProjectCreate(
        id=project_id,
        user_id=user_id,
    )
    return await project_create.save()


async def add_message(
    project_id: str,
    role: str,
    content: str,
    message_metadata: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> ConversationMessage:
    """Add a message to a conversation project."""
    # Ensure project exists
    await create_or_get_project(project_id, user_id)

    # Create and save message
    message_create = ConversationMessageCreate(
        project_id=project_id,
        role=role,
        content=content,
        message_metadata=message_metadata,
    )
    message = await message_create.save()

    # Update project activity
    project = await ConversationProject.get(project_id)
    if project:
        await project.update_activity()

    return message


async def get_conversation_history(
    project_id: str, user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get conversation history for a project."""
    messages = await ConversationMessage.get_by_project(project_id, user_id)

    if not messages:
        raise ValueError(f"No conversation found for project {project_id}")

    # Convert to dict format expected by API
    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "metadata": message.message_metadata or {},
            "created_at": message.created_at.isoformat(),
        }
        for message in messages
    ]


async def get_projects_by_user(
    user_id: Optional[str] = None, limit: int = 50
) -> List[Dict[str, Any]]:
    """Get projects by user with their conversation history."""
    projects = await ConversationProject.get_by_user(user_id, limit)

    result = []
    for project in projects:
        # Get conversation history for each project
        try:
            conversation_history = await get_conversation_history(project.id, user_id)
        except ValueError:
            # No conversation history for this project
            conversation_history = []

        result.append(
            {
                "project_id": project.id,
                "user_id": project.user_id,
                "created_at": project.created_at.isoformat(),
                "last_activity": project.last_activity.isoformat(),
                "message_count": len(conversation_history),
                "last_message": conversation_history[-1]
                if conversation_history
                else None,
                "first_message": conversation_history[0]
                if conversation_history
                else None,
                "conversation_history": conversation_history,
            }
        )

    return result


async def get_project_metadata(project_id: str) -> Optional[Dict[str, Any]]:
    """Get project metadata."""
    project = await ConversationProject.get(project_id)
    if not project:
        return None

    return {
        "user_id": project.user_id,
        "created_at": project.created_at.timestamp(),
        "last_activity": project.last_activity.timestamp(),
    }
