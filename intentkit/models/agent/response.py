from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, override

from pydantic import ConfigDict
from pydantic import Field as PydanticField
from pydantic.json_schema import SkipJsonSchema
from pydantic.main import IncEx

from intentkit.models.agent.agent import Agent
from intentkit.models.agent.public_info import AgentExample
from intentkit.models.agent_data import AgentData


class AgentResponse(Agent):
    """Agent response model that excludes sensitive fields from JSON output and schema."""

    model_config = ConfigDict(
        title="AgentPublic",
        from_attributes=True,
        # json_encoders={
        #     datetime: lambda v: v.isoformat(timespec="milliseconds"),
        # },
    )

    # Override privacy fields to exclude them from JSON schema
    purpose: SkipJsonSchema[str | None] = None
    personality: SkipJsonSchema[str | None] = None
    principles: SkipJsonSchema[str | None] = None
    prompt: SkipJsonSchema[str | None] = None
    prompt_append: SkipJsonSchema[str | None] = None
    temperature: SkipJsonSchema[float | None] = None
    frequency_penalty: SkipJsonSchema[float | None] = None
    telegram_entrypoint_prompt: SkipJsonSchema[str | None] = None
    telegram_config: SkipJsonSchema[dict[str, Any] | None] = None
    discord_config: SkipJsonSchema[dict[str, Any] | None] = None
    xmtp_entrypoint_prompt: SkipJsonSchema[str | None] = None

    # Additional fields specific to AgentResponse
    cdp_wallet_address: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="CDP wallet address of the agent",
        ),
    ]
    evm_wallet_address: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="EVM wallet address of the agent",
        ),
    ]
    solana_wallet_address: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Solana wallet address of the agent",
        ),
    ]
    has_twitter_linked: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent has Twitter linked",
        ),
    ]
    linked_twitter_username: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Linked Twitter username",
        ),
    ]
    linked_twitter_name: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Linked Twitter display name",
        ),
    ]
    has_twitter_self_key: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent has Twitter self key",
        ),
    ]
    has_telegram_self_key: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent has Telegram self key",
        ),
    ]
    linked_telegram_username: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Linked Telegram username",
        ),
    ]
    linked_telegram_name: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Linked Telegram display name",
        ),
    ]
    accept_image_input: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent accepts image input",
        ),
    ]
    accept_image_input_private: Annotated[
        bool,
        PydanticField(
            default=False,
            description="Whether the agent accepts image input in private mode",
        ),
    ]

    def etag(self) -> str:
        """Generate an ETag for this agent response.

        The ETag is based on a hash of the entire object to ensure it changes
        whenever any part of the agent is modified.

        Returns:
            str: ETag value for the agent
        """

        # Generate hash from the entire object data using json mode to handle datetime objects
        # Sort keys to ensure consistent ordering of dictionary keys
        data = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return f"{hashlib.md5(data.encode()).hexdigest()}"

    @classmethod
    async def from_agent(
        cls, agent: Agent, agent_data: AgentData | None = None
    ) -> "AgentResponse":
        """Create an AgentResponse from an Agent instance.

        Args:
            agent: Agent instance
            agent_data: Optional AgentData instance

        Returns:
            AgentResponse: Response model with additional processed data
        """
        # Process CDP wallet address
        cdp_wallet_address = agent_data.evm_wallet_address if agent_data else None
        evm_wallet_address = agent_data.evm_wallet_address if agent_data else None
        solana_wallet_address = agent_data.solana_wallet_address if agent_data else None

        # Process Twitter linked status
        has_twitter_linked = False
        linked_twitter_username = None
        linked_twitter_name = None
        if agent_data and agent_data.twitter_access_token:
            linked_twitter_username = agent_data.twitter_username
            linked_twitter_name = agent_data.twitter_name
            if agent_data.twitter_access_token_expires_at:
                has_twitter_linked = (
                    agent_data.twitter_access_token_expires_at > datetime.now(UTC)
                )
            else:
                has_twitter_linked = True

        # Process Twitter self-key status
        has_twitter_self_key = bool(
            agent_data and agent_data.twitter_self_key_refreshed_at
        )

        # Process Telegram self-key status
        linked_telegram_username = None
        linked_telegram_name = None
        telegram_config = agent.telegram_config or {}
        has_telegram_self_key = bool(
            telegram_config and "token" in telegram_config and telegram_config["token"]
        )
        if telegram_config and "token" in telegram_config:
            if agent_data:
                linked_telegram_username = agent_data.telegram_username
                linked_telegram_name = agent_data.telegram_name

        accept_image_input = (
            await agent.is_model_support_image() or agent.has_image_parser_skill()
        )
        accept_image_input_private = (
            await agent.is_model_support_image()
            or agent.has_image_parser_skill(is_private=True)
        )

        # Create AgentResponse instance directly from agent with additional fields
        return cls(
            # Copy all fields from agent
            **agent.model_dump(),
            # Add computed fields
            cdp_wallet_address=cdp_wallet_address,
            evm_wallet_address=evm_wallet_address,
            solana_wallet_address=solana_wallet_address,
            has_twitter_linked=has_twitter_linked,
            linked_twitter_username=linked_twitter_username,
            linked_twitter_name=linked_twitter_name,
            has_twitter_self_key=has_twitter_self_key,
            has_telegram_self_key=has_telegram_self_key,
            linked_telegram_username=linked_telegram_username,
            linked_telegram_name=linked_telegram_name,
            accept_image_input=accept_image_input,
            accept_image_input_private=accept_image_input_private,
        )

    @override
    def model_dump(
        self,
        *,
        mode: Literal["json", "python"] | str = "python",
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        exclude_computed_fields: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        """Override model_dump to exclude privacy fields and filter data."""
        # Get the base model dump
        data = super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            exclude_computed_fields=exclude_computed_fields,
            round_trip=round_trip,
            warnings=warnings,
            fallback=fallback,
            serialize_as_any=serialize_as_any,
        )

        # Remove privacy fields that might still be present
        privacy_fields = {
            "purpose",
            "personality",
            "principles",
            "prompt",
            "prompt_append",
            "temperature",
            "frequency_penalty",
            "telegram_entrypoint_prompt",
            "telegram_config",
            "discord_config",
            "xmtp_entrypoint_prompt",
        }
        for field in privacy_fields:
            data.pop(field, None)

        # Filter autonomous list to only keep safe fields
        if "autonomous" in data and data["autonomous"]:
            filtered_autonomous = []
            for item in data["autonomous"]:
                if isinstance(item, dict):
                    # Only keep safe fields: id, name, description, enabled
                    filtered_item = {
                        key: item[key]
                        for key in ["id", "name", "description", "enabled"]
                        if key in item
                    }
                    filtered_autonomous.append(filtered_item)
                else:
                    # Handle AgentAutonomous objects
                    item_dict = (
                        item.model_dump() if hasattr(item, "model_dump") else dict(item)
                    )
                    # Only keep safe fields: id, name, description, enabled
                    filtered_item = {
                        key: item_dict[key]
                        for key in ["id", "name", "description", "enabled"]
                        if key in item_dict
                    }
                    filtered_autonomous.append(filtered_item)
            data["autonomous"] = filtered_autonomous

        # Convert examples to AgentExample instances if they're dictionaries
        if "examples" in data and data["examples"]:
            converted_examples = []
            for example in data["examples"]:
                if isinstance(example, dict):
                    converted_examples.append(AgentExample(**example).model_dump())
                else:
                    converted_examples.append(
                        example.model_dump()
                        if hasattr(example, "model_dump")
                        else example
                    )
            data["examples"] = converted_examples

        # Filter skills to only include enabled ones with specific configurations
        if "skills" in data and data["skills"]:
            filtered_skills = {}
            for skill_name, skill_config in data["skills"].items():
                if (
                    isinstance(skill_config, dict)
                    and skill_config.get("enabled") is True
                ):
                    # Filter out disabled states from the skill configuration
                    original_states = skill_config.get("states", {})
                    filtered_states = {
                        state_name: state_value
                        for state_name, state_value in original_states.items()
                        if state_value != "disabled"
                    }

                    # Only include the skill if it has at least one non-disabled state
                    if filtered_states:
                        filtered_config = {
                            "enabled": skill_config["enabled"],
                            "states": filtered_states,
                        }
                        # Add other non-sensitive config fields if needed
                        for key in ["public", "private"]:
                            if key in skill_config:
                                filtered_config[key] = skill_config[key]
                        filtered_skills[skill_name] = filtered_config
            data["skills"] = filtered_skills

        return data

    @override
    def model_dump_json(
        self,
        *,
        indent: int | None = None,
        ensure_ascii: bool = False,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        exclude_computed_fields: bool = False,
        round_trip: bool = False,
        warnings: bool | Literal["none", "warn", "error"] = True,
        fallback: Callable[[Any], Any] | None = None,
        serialize_as_any: bool = False,
    ) -> str:
        """Override model_dump_json to exclude privacy fields and filter sensitive data."""
        # Get the filtered data using the same logic as model_dump
        data = self.model_dump(
            mode="json",
            include=include,
            exclude=exclude,
            context=context,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            exclude_computed_fields=exclude_computed_fields,
            round_trip=round_trip,
            warnings=warnings,
            fallback=fallback,
            serialize_as_any=serialize_as_any,
        )

        # Use json.dumps to serialize the filtered data with proper indentation
        return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
