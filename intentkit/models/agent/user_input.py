from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, ClassVar

from epyxid import XID
from pydantic import ConfigDict, field_validator
from pydantic import Field as PydanticField

from intentkit.models.agent.core import AgentCore, AgentVisibility

# Forbidden markdown heading patterns, precompiled: these validators run on
# every agent hydration and scan prompts up to 200k chars.
_LEVEL1_HEADING = re.compile(r"^# ", re.MULTILINE)
_LEVEL1_LEVEL2_HEADING = re.compile(r"^(# |## )", re.MULTILINE)


class AgentUserInput(AgentCore):
    """Agent update model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        title="AgentUserInput",
        from_attributes=True,
        json_schema_extra={
            "required": ["name"],
        },
    )

    slug: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="URL-friendly slug for the agent. Once set, cannot be changed.",
            min_length=2,
            max_length=60,
            pattern=r"^[a-z]([a-z0-9-]*[a-z0-9])?$",
        ),
    ] = None
    # if telegram_entrypoint_enabled, the telegram_entrypoint_enabled will be enabled, telegram_config will be checked
    telegram_entrypoint_enabled: Annotated[
        bool | None,
        PydanticField(
            default=False,
            description="Whether the agent can play telegram bot",
        ),
    ] = False
    telegram_entrypoint_prompt: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Extra prompt for telegram entrypoint",
            max_length=10000,
        ),
    ] = None
    telegram_config: Annotated[
        dict[str, object] | None,
        PydanticField(
            default=None,
            description="Telegram integration configuration settings",
        ),
    ] = None
    discord_entrypoint_enabled: Annotated[
        bool | None,
        PydanticField(
            default=False,
            description="Whether the agent can play discord bot",
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ] = False
    discord_config: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Discord integration configuration settings including token, whitelists, and behavior settings",
            json_schema_extra={
                "x-group": "entrypoint",
            },
        ),
    ] = None
    xmtp_entrypoint_prompt: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Extra prompt for xmtp entrypoint, xmtp support is in beta",
            max_length=10000,
        ),
    ] = None
    wechat_entrypoint_prompt: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Extra prompt for wechat entrypoint",
            max_length=10000,
        ),
    ] = None


class AgentUpdate(AgentUserInput):
    """Agent update model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        title="Agent",
        from_attributes=True,
        json_schema_extra={
            "required": ["name"],
        },
    )

    upstream_id: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="External reference ID for idempotent operations",
            max_length=100,
        ),
    ] = None
    upstream_extra: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Additional data store for upstream use",
            json_schema_extra={
                "x-group": "internal",
            },
        ),
    ] = None
    extra_prompt: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Only when the agent is created from a template.",
            max_length=20000,
        ),
    ] = None
    visibility: Annotated[
        AgentVisibility | None,
        PydanticField(
            default=None,
            description="Visibility level of the agent: PRIVATE(0), TEAM(10), or PUBLIC(20)",
        ),
    ] = None
    archived_at: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Timestamp when the agent was archived. NULL means not archived",
        ),
    ] = None

    @staticmethod
    def _reject_headings(
        v: str | None, pattern: re.Pattern[str], message: str
    ) -> str | None:
        """Reject text where any line matches the forbidden heading pattern."""
        if v is not None and pattern.search(v):
            raise ValueError(message)
        return v

    @field_validator("system_prompt")
    @classmethod
    def validate_no_level1_headings(cls, v: str | None) -> str | None:
        """Validate that the text doesn't contain level 1 headings."""
        return cls._reject_headings(
            v,
            _LEVEL1_HEADING,
            "Level 1 headings (#) are not allowed. Please use level 2+ headings (##, ###, etc.) instead.",
        )

    @field_validator(
        "extra_prompt",
        "sub_agent_prompt",
    )
    @classmethod
    def validate_no_level1_level2_headings(cls, v: str | None) -> str | None:
        """Validate that the text doesn't contain level 1 or level 2 headings."""
        return cls._reject_headings(
            v,
            _LEVEL1_LEVEL2_HEADING,
            "Level 1 and 2 headings (# and ##) are not allowed. Please use level 3+ headings (###, ####, etc.) instead.",
        )


class AgentCreate(AgentUpdate):
    """Agent create model."""

    id: Annotated[
        str,
        PydanticField(
            default_factory=lambda: str(XID()),
            description="Unique identifier for the agent. Must be URL-safe, containing only lowercase letters, numbers, and hyphens",
            pattern=r"^[a-z][a-z0-9-]*$",
            min_length=2,
            max_length=67,
        ),
    ]
    owner: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Owner identifier of the agent, used for access control",
            max_length=50,
        ),
    ] = None
    team_id: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Team identifier of the agent",
            max_length=50,
        ),
    ] = None
    template_id: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Template identifier of the agent",
            max_length=50,
        ),
    ] = None
