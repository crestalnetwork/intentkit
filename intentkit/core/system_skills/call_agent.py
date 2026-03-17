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
CALL_AGENT_TIMEOUT = 600  # 10 minutes

# Maximum recursion depth for nested call_agent invocations
MAX_CALL_DEPTH = 5


class CallAgentInput(BaseModel):
    """Input schema for calling another agent."""

    agent_id: str = Field(..., description="Target agent ID or slug")
    message: str = Field(..., description="Message to send")


class CallAgentSkill(SystemSkill):
    """Skill for calling another agent and getting its response.

    This skill allows an agent to delegate tasks to other agents
    by calling them with a message and receiving their final response.
    """

    name: str = "call_agent"
    description: str = "Delegate a task to another agent by sending it a message and receiving its response."
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
        from intentkit.core.agent import get_agent_by_id_or_slug
        from intentkit.core.engine import execute_agent

        try:
            context = self.get_context()

            # Check recursion depth before proceeding
            if context.call_depth >= MAX_CALL_DEPTH:
                raise ToolException(
                    f"Maximum call_agent recursion depth ({MAX_CALL_DEPTH}) exceeded. "
                    "Cannot call another agent from this depth."
                )

            # Resolve agent_id (could be a slug)
            resolved_agent = await get_agent_by_id_or_slug(agent_id)
            if not resolved_agent:
                raise ToolException(f"Agent '{agent_id}' not found")
            actual_agent_id = resolved_agent.id

            # Enforce sub-agents whitelist
            allowed = context.agent.sub_agents
            if allowed is not None:
                slug = resolved_agent.slug
                if (
                    agent_id not in allowed
                    and actual_agent_id not in allowed
                    and (not slug or slug not in allowed)
                ):
                    raise ToolException(
                        f"Agent '{agent_id}' is not in the allowed sub-agents list"
                    )

            # Create a chat message for the called agent
            # Inherit context from the current skill execution
            chat_message = ChatMessageCreate(
                id=str(XID()),
                agent_id=actual_agent_id,
                chat_id=f"call-{context.agent_id}-{context.chat_id}",
                user_id=context.user_id,
                author_id=context.agent_id,
                author_type=AuthorType.INTERNAL,
                thread_type=context.entrypoint,
                message=message,
                call_depth=context.call_depth + 1,
            )

            # Execute the called agent with a timeout
            async with asyncio.timeout(CALL_AGENT_TIMEOUT):
                results = await execute_agent(chat_message)

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

        except TimeoutError as e:
            self.logger.error(
                "call_agent timed out after %ss waiting for agent '%s'",
                CALL_AGENT_TIMEOUT,
                agent_id,
            )
            raise ToolException(
                f"Agent '{agent_id}' did not respond within "
                f"{CALL_AGENT_TIMEOUT} seconds"
            ) from e
        except ToolException:
            raise
        except Exception as e:
            self.logger.error("call_agent failed: %s", e, exc_info=True)
            raise ToolException(f"Call agent failed with error: {e}") from e
