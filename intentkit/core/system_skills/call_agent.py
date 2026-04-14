"""Skill for calling another agent."""

import asyncio
from typing import Literal, override

from epyxid import XID
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.core.system_skills.base import SystemSkill
from intentkit.models.chat import (
    AuthorType,
    ChatMessageAttachment,
    ChatMessageAttachmentType,
    ChatMessageCreate,
)

# Default timeout for calling another agent (in seconds)
CALL_AGENT_TIMEOUT = 600  # 10 minutes

# Maximum recursion depth for nested call_agent invocations
MAX_CALL_DEPTH = 5


def _xmtp_description(data: dict[str, object]) -> str | None:
    """Pull the user-facing description from an XMTP wallet_send_calls payload."""
    calls = data.get("calls")
    if not isinstance(calls, list) or not calls:
        return None
    first = calls[0]
    if not isinstance(first, dict):
        return None
    metadata = first.get("metadata")
    if not isinstance(metadata, dict):
        return None
    desc = metadata.get("description")
    return str(desc) if desc else None


def render_attachments_awareness(
    attachments: list[ChatMessageAttachment],
) -> str:
    """Render a notice block telling the caller's LLM which attachments were sent.

    Sub-agents deliver attachments (images, links, cards, etc.) to the user
    directly through their own messages. The caller only receives the final
    text via the tool result, so without this notice it may redundantly
    re-describe or resend the same content.
    """
    if not attachments:
        return ""

    lines: list[str] = [
        "",
        "---",
        "",
        (
            "The following attachments have already been sent to the user. "
            "They are listed here for your awareness only — do not resend or "
            "re-describe them to the user."
        ),
        "",
    ]

    for i, att in enumerate(attachments, start=1):
        att_type = att["type"]
        # JSONB round-trips the enum as its string value, so att_type may be
        # either the enum or a raw str at runtime. Both compare equal under
        # `match` because ChatMessageAttachmentType inherits from str.
        type_label = (
            att_type.value
            if isinstance(att_type, ChatMessageAttachmentType)
            else att_type
        )
        lead_text = att["lead_text"]
        url = att["url"]
        data = att.get("json") or {}

        fragments: list[str] = []
        if lead_text:
            fragments.append(f'lead_text="{lead_text}"')

        match att_type:
            case (
                ChatMessageAttachmentType.IMAGE
                | ChatMessageAttachmentType.VIDEO
                | ChatMessageAttachmentType.FILE
                | ChatMessageAttachmentType.LINK
            ):
                if url:
                    fragments.append(f"url={url}")
            case ChatMessageAttachmentType.XMTP:
                # Payload is a wallet_send_calls dict in `json`. Surface the
                # first call's metadata.description (a user-visible summary)
                # instead of raw calldata, which is long hex and unhelpful.
                desc = _xmtp_description(data)
                if desc:
                    fragments.append(f'description="{desc}"')
            case ChatMessageAttachmentType.CARD:
                for key in ("title", "description", "label", "image_url"):
                    val = data.get(key)
                    if val:
                        fragments.append(f'{key}="{val}"')
                if url:
                    fragments.append(f"url={url}")
            case ChatMessageAttachmentType.CHOICE:
                option_parts: list[str] = []
                for key in sorted(data.keys()):
                    value = data[key]
                    if isinstance(value, dict):
                        option_parts.append(f'{key}="{value.get("title", "")}"')
                    else:
                        option_parts.append(f"{key}={value!r}")
                if option_parts:
                    fragments.append("options=[" + ", ".join(option_parts) + "]")

        body = " | ".join(fragments) if fragments else "(no details)"
        lines.append(f"{i}. [{type_label}] {body}")

    return "\n".join(lines)


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
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    @override
    async def _arun(
        self,
        agent_id: str,
        message: str,
    ) -> tuple[str, list[ChatMessageAttachment]]:
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
                chat_id=f"call-{XID()}",
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

            # Collect all attachments from the message queue
            all_attachments: list[ChatMessageAttachment] = []
            for msg in results:
                if msg.attachments:
                    all_attachments.extend(msg.attachments)

            # Get the last message from the results
            last_message = results[-1]

            # Check if the last message is from the agent
            if last_message.author_type == AuthorType.AGENT:
                response_text = last_message.message + render_attachments_awareness(
                    all_attachments
                )
                return response_text, all_attachments

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
