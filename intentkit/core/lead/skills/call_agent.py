"""Team-aware call_agent skill for the lead agent."""

from __future__ import annotations

import asyncio
from typing import Literal, override

from epyxid import XID
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.abstracts.graph import AgentContext
from intentkit.core.lead.skills.base import LeadSkill
from intentkit.core.system_skills.call_agent import (
    CALL_AGENT_TIMEOUT,
    MAX_CALL_DEPTH,
    render_attachments_awareness,
)
from intentkit.models.chat import (
    AuthorType,
    ChatMessage,
    ChatMessageAttachment,
    ChatMessageCreate,
)


class LeadCallAgentInput(BaseModel):
    """Input schema for calling a sub-agent."""

    agent_id: str = Field(..., description="Target agent ID or slug")
    message: str = Field(..., description="Message to send")


class LeadCallAgent(LeadSkill):
    """Team-aware call_agent that supports both in-memory sub-agents and DB agents.

    Resolution order:
    1. Check in-memory sub-agent registry (agent-manager, task-manager, etc.)
    2. Fall back to database agent lookup (scoped to team)
    """

    name: str = "lead_call_agent"
    description: str = "Delegate a task to a sub-agent by sending it a message and receiving its response."
    args_schema: ArgsSchema | None = LeadCallAgentInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    @override
    async def _arun(
        self,
        agent_id: str,
        message: str,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        try:
            context = self.get_context()

            if context.call_depth >= MAX_CALL_DEPTH:
                raise ToolException(
                    f"Maximum call_agent recursion depth ({MAX_CALL_DEPTH}) exceeded. "
                    "Cannot call another agent from this depth."
                )

            from intentkit.core.lead.sub_agents import (
                SUB_AGENT_REGISTRY,
            )

            team_id = context.team_id
            if not team_id:
                raise ToolException("No team_id in context")

            if agent_id in SUB_AGENT_REGISTRY:
                return await self._call_sub_agent(context, agent_id, message, team_id)

            return await self._call_db_agent(context, agent_id, message)

        except TimeoutError as e:
            self.logger.error(
                "lead_call_agent timed out after %ss for '%s'",
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
            self.logger.error("lead_call_agent failed: %s", e, exc_info=True)
            raise ToolException(f"Call agent failed with error: {e}") from e

    async def _call_sub_agent(
        self,
        context: AgentContext,
        slug: str,
        message: str,
        team_id: str,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Call an in-memory sub-agent via stream_agent_raw."""
        from intentkit.core.engine import stream_agent_raw
        from intentkit.core.lead.sub_agents import get_sub_agent_executor

        executor, sub_agent = await get_sub_agent_executor(team_id, slug)

        chat_message = self._build_chat_message(context, sub_agent.id, team_id, message)

        all_attachments: list[ChatMessageAttachment] = []
        last_message = None

        async with asyncio.timeout(CALL_AGENT_TIMEOUT):
            async for chat_msg in stream_agent_raw(chat_message, sub_agent, executor):
                if chat_msg.attachments:
                    all_attachments.extend(chat_msg.attachments)
                last_message = chat_msg

        return self._check_response(last_message, all_attachments, slug)

    async def _call_db_agent(
        self,
        context: AgentContext,
        agent_id: str,
        message: str,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Call a database agent, scoped to the same team."""
        from intentkit.core.agent import get_agent_by_id_or_slug
        from intentkit.core.engine import execute_agent

        resolved_agent = await get_agent_by_id_or_slug(agent_id)
        if not resolved_agent:
            raise ToolException(f"Agent '{agent_id}' not found")

        if resolved_agent.team_id != context.team_id:
            raise ToolException(f"Agent '{agent_id}' does not belong to this team")

        chat_message = self._build_chat_message(
            context, resolved_agent.id, context.team_id, message
        )

        async with asyncio.timeout(CALL_AGENT_TIMEOUT):
            results = await execute_agent(chat_message)

        if not results:
            raise ToolException(f"No response received from agent '{agent_id}'")

        all_attachments: list[ChatMessageAttachment] = []
        for msg in results:
            if msg.attachments:
                all_attachments.extend(msg.attachments)

        return self._check_response(results[-1], all_attachments, agent_id)

    @staticmethod
    def _build_chat_message(
        context: AgentContext,
        target_agent_id: str,
        team_id: str | None,
        message: str,
    ) -> ChatMessageCreate:
        """Build a ChatMessageCreate for calling a sub-agent."""
        return ChatMessageCreate(
            id=str(XID()),
            agent_id=target_agent_id,
            chat_id=f"call-{XID()}",
            user_id=context.user_id,
            author_id=context.agent_id,
            author_type=AuthorType.INTERNAL,
            thread_type=context.entrypoint,
            team_id=team_id,
            message=message,
            call_depth=context.call_depth + 1,
        )

    @staticmethod
    def _check_response(
        last_message: ChatMessage | None,
        all_attachments: list[ChatMessageAttachment],
        agent_id: str,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Validate the last message and return response text + attachments."""
        if not last_message:
            raise ToolException(f"No response received from agent '{agent_id}'")

        if last_message.author_type == AuthorType.AGENT:
            response_text = last_message.message + render_attachments_awareness(
                all_attachments
            )
            return response_text, all_attachments

        if last_message.author_type == AuthorType.SYSTEM:
            error_info = ""
            if last_message.error_type:
                error_info = f" (error_type: {last_message.error_type})"
            raise ToolException(
                f"Agent '{agent_id}' returned a system error{error_info}: "
                f"{last_message.message}"
            )

        raise ToolException(
            f"Agent '{agent_id}' did not return an agent response. "
            f"Last message type: {last_message.author_type}"
        )


lead_call_agent_skill = LeadCallAgent()
