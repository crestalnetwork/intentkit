"""Skill for calling another agent."""

from typing import cast, override

from epyxid import XID
from langchain_core.tools import BaseTool
from langgraph.runtime import get_runtime
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.models.chat import AuthorType, ChatMessageCreate


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


class CallAgentSkill(BaseTool):
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
    args_schema: type[BaseModel] = CallAgentInput  # pyright: ignore[reportIncompatibleVariableOverride]

    @override
    def _run(
        self,
        agent_id: str,
        message: str,
    ) -> str:
        raise NotImplementedError(
            "Use _arun instead, IntentKit only supports asynchronous skill calls"
        )

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
        """
        # Import here to avoid circular dependency
        # When initializing an agent, it may import this skill,
        # and this skill imports engine, which imports skills
        from intentkit.core.engine import execute_agent

        runtime = get_runtime(AgentContext)
        context = cast(AgentContext | None, runtime.context)
        if context is None:
            raise ValueError("No AgentContext found")

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

        # Execute the called agent
        results = await execute_agent(chat_message)

        if not results:
            return "No response received from the called agent"

        # Get the last message from the results
        last_message = results[-1]
        return last_message.message
