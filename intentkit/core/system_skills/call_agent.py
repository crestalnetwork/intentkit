"""Skill for calling another agent."""

import asyncio
from typing import override

from epyxid import XID
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_skills.base import SystemSkill
from intentkit.models.chat import AuthorType, ChatMessageCreate

# Default timeout for calling another agent (in seconds)
CALL_AGENT_TIMEOUT = 180  # 3 minutes


class CallAgentInput(BaseModel):
    """Input schema for calling another agent."""

    agent_id: str = Field(
        ...,
        description="The ID of the agent to call",
    )
    message: str = Field(
        ...,
        description="The message to send to the agent",
    )


class CallAgentSkill(SystemSkill):
    """Skill for calling another agent and getting its response.

    This skill allows an agent to delegate tasks to other agents
    by calling them with a message and receiving their final response.
    """

    name: str = "call_agent"
    description: str = (
        "Call another agent with a message and get its response. "
        "This allows the current agent to delegate tasks to other agents. "
        "The called agent will execute with the provided message and return its final response."
    )
    args_schema: ArgsSchema | None = CallAgentInput

    @override
    async def _arun(
        self,
        agent_id: str,
        message: str,
    ) -> str:
        """Call another agent and return its response.

        Args:
            agent_id: The ID of the agent to call.
            message: The message to send to the agent.

        Returns:
            The response message from the called agent.

        Raises:
            ToolException: If no response received, timeout, or the last message is not from agent.
        """
        # Import here to avoid circular dependency
        # When initializing an agent, it may import this skill,
        # and this skill imports engine, which imports skills
        from intentkit.core.engine import execute_agent

        context = self.get_context()

        # Create a chat message for the called agent
        # Inherit context from the current skill execution
        chat_message = ChatMessageCreate(
            id=str(XID()),
            agent_id=agent_id,
            chat_id=f"call-{context.agent_id}-{context.chat_id}",
            user_id=context.user_id,
            author_id=context.agent_id,
            author_type=AuthorType.INTERNAL,
            thread_type=context.entrypoint,
            message=message,
        )

        # Execute the called agent with a timeout
        try:
            async with asyncio.timeout(CALL_AGENT_TIMEOUT):
                results = await execute_agent(chat_message)
        except TimeoutError:
            self.logger.error(
                f"call_agent timed out after {CALL_AGENT_TIMEOUT}s "
                f"waiting for agent '{agent_id}'"
            )
            raise ToolException(
                f"Agent '{agent_id}' did not respond within "
                f"{CALL_AGENT_TIMEOUT} seconds"
            )

        if not results:
            raise ToolException(
                f"No response received from the called agent '{agent_id}'"
            )

        # Get the last message from the results
        last_message = results[-1]

        # Check if the last message is from the agent
        if last_message.author_type == AuthorType.AGENT:
            return last_message.message

        # If the last message is a system message, include the error details
        if last_message.author_type == AuthorType.SYSTEM:
            error_info = ""
            if last_message.error_type:
                error_info = f" (error_type: {last_message.error_type})"
            raise ToolException(
                f"Agent '{agent_id}' returned a system error{error_info}: {last_message.message}"
            )

        # For other message types (skill, etc.), raise an exception
        raise ToolException(
            f"Agent '{agent_id}' did not return an agent response. "
            + f"Last message type: {last_message.author_type}"
        )
