from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, ClassVar

from cron_validator import CronValidator
from epyxid import XID
from pydantic import ConfigDict, field_validator
from pydantic import Field as PydanticField

from intentkit.models.agent.autonomous import AgentAutonomous
from intentkit.models.agent.core import AgentCore, AgentVisibility
from intentkit.utils.error import IntentKitAPIError


class AgentUserInput(AgentCore):
    """Agent update model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        title="AgentUserInput",
        from_attributes=True,
        json_schema_extra={
            "required": ["name"],
        },
    )

    # only when wallet privder is readonly
    readonly_wallet_address: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Address of the agent's wallet, only used when wallet_provider is readonly. Agent will not be able to sign transactions.",
        ),
    ] = None
    # only when wallet provider is privy
    weekly_spending_limit: Annotated[
        float | None,
        PydanticField(
            default=None,
            description="Weekly spending limit in USDC when wallet_provider is safe. This limits how much USDC the agent can spend per week.",
            ge=0.0,
        ),
    ] = None
    # autonomous mode
    autonomous: Annotated[
        list[AgentAutonomous] | None,
        PydanticField(
            default=None,
            description=("Autonomous agent configurations."),
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

    @field_validator(
        "purpose",
        "personality",
        "principles",
        "prompt",
        "prompt_append",
        "extra_prompt",
    )
    @classmethod
    def validate_no_level1_level2_headings(cls, v: str | None) -> str | None:
        """Validate that the text doesn't contain level 1 or level 2 headings."""
        if v is None:
            return v

        import re

        # Check if any line starts with # or ## followed by a space
        if re.search(r"^(# |## )", v, re.MULTILINE):
            raise ValueError(
                "Level 1 and 2 headings (# and ##) are not allowed. Please use level 3+ headings (###, ####, etc.) instead."
            )
        return v

    def validate_autonomous_schedule(self) -> None:
        """Validate the schedule settings for autonomous configurations.

        This validation ensures:
        1. Only one scheduling method (minutes or cron) is set per autonomous config
        2. The minimum interval is 5 minutes for both types of schedules
        """
        if not self.autonomous:
            return

        for autonomous_config in self.autonomous:
            # Check that exactly one scheduling method is provided
            if not autonomous_config.minutes and not autonomous_config.cron:
                raise IntentKitAPIError(
                    status_code=400,
                    key="InvalidAutonomousConfig",
                    message="either minutes or cron must have a value",
                )

            if autonomous_config.minutes and autonomous_config.cron:
                raise IntentKitAPIError(
                    status_code=400,
                    key="InvalidAutonomousConfig",
                    message="only one of minutes or cron can be set",
                )

            # Validate minimum interval of 5 minutes
            if autonomous_config.minutes and autonomous_config.minutes < 5:
                raise IntentKitAPIError(
                    status_code=400,
                    key="InvalidAutonomousInterval",
                    message="The shortest execution interval is 5 minutes",
                )

            # Validate cron expression to ensure interval is at least 5 minutes
            if autonomous_config.cron:
                # First validate the cron expression format using cron-validator

                try:
                    _ = CronValidator.parse(autonomous_config.cron)
                except ValueError:
                    raise IntentKitAPIError(
                        status_code=400,
                        key="InvalidCronExpression",
                        message=f"Invalid cron expression format: {autonomous_config.cron}",
                    )

                parts = autonomous_config.cron.split()
                if len(parts) < 5:
                    raise IntentKitAPIError(
                        status_code=400,
                        key="InvalidCronExpression",
                        message="Invalid cron expression format",
                    )

                minute, hour, *_ = parts[:5]

                # Check if minutes or hours have too frequent intervals
                if "*" in minute and "*" in hour:
                    # If both minute and hour are wildcards, it would run every minute
                    raise IntentKitAPIError(
                        status_code=400,
                        key="InvalidAutonomousInterval",
                        message="The shortest execution interval is 5 minutes",
                    )

                if "/" in minute:
                    # Check step value in minute field (e.g., */15)
                    step = int(minute.split("/")[1])
                    if step < 5 and hour == "*":
                        raise IntentKitAPIError(
                            status_code=400,
                            key="InvalidAutonomousInterval",
                            message="The shortest execution interval is 5 minutes",
                        )

                # Check for comma-separated values or ranges that might result in multiple executions per hour
                if ("," in minute or "-" in minute) and hour == "*":
                    raise IntentKitAPIError(
                        status_code=400,
                        key="InvalidAutonomousInterval",
                        message="The shortest execution interval is 5 minutes",
                    )

    @staticmethod
    def normalize_autonomous_statuses(
        tasks: list[AgentAutonomous] | list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]] | None:
        if not tasks:
            return None
        normalized: list[dict[str, Any]] = []
        for task in tasks:
            model = (
                task
                if isinstance(task, AgentAutonomous)
                else AgentAutonomous.model_validate(task)
            )
            normalized.append(model.normalize_status_defaults().model_dump())
        return normalized


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
