from __future__ import annotations

import json
import logging
import textwrap
import warnings
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, ClassVar

import jsonref
import yaml
from pydantic import ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent.public_info import AgentPublicInfo
from intentkit.models.agent.user_input import AgentCreate, AgentUpdate
from intentkit.models.credit import CreditAccount
from intentkit.models.llm import LLMModelInfo

logger = logging.getLogger(__name__)


class Agent(AgentCreate, AgentPublicInfo):
    """Agent model."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    version: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Version hash of the agent",
        ),
    ] = None
    statistics: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Statistics of the agent, update every 1 hour for query",
        ),
    ] = None
    assets: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Assets of the agent, update every 1 hour for query",
        ),
    ] = None
    account_snapshot: Annotated[
        CreditAccount | None,
        PydanticField(
            default=None,
            description="Account snapshot of the agent, update every 1 hour for query",
        ),
    ] = None
    extra: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Other helper data fields for query, come from agent and agent data",
        ),
    ] = None
    deployed_at: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Timestamp when the agent was deployed",
        ),
    ] = None
    public_info_updated_at: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Timestamp when the agent public info was last updated",
        ),
    ] = None
    # auto timestamp
    created_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when the agent was created, will ignore when importing"
        ),
    ]
    updated_at: Annotated[
        datetime,
        PydanticField(
            description="Timestamp when the agent was last updated, will ignore when importing"
        ),
    ]

    def has_image_parser_skill(self, is_private: bool = False) -> bool:
        if self.skills:
            for skill, skill_config in self.skills.items():
                if skill == "openai" and skill_config.get("enabled"):
                    states = skill_config.get("states", {})
                    if is_private:
                        # Include both private and public when is_private=True
                        if states.get("image_to_text") in ["private", "public"]:
                            return True
                        if states.get("gpt_image_to_image") in ["private", "public"]:
                            return True
                    else:
                        # Only public when is_private=False
                        if states.get("image_to_text") in ["public"]:
                            return True
                        if states.get("gpt_image_to_image") in ["public"]:
                            return True
        return False

    async def is_model_support_image(self) -> bool:
        try:
            model = await LLMModelInfo.get(self.model)
            return model.supports_image_input
        except Exception:
            return False

    def to_yaml(self) -> str:
        """
        Dump the agent model to YAML format with field descriptions as comments.
        The comments are extracted from the field descriptions in the model.
        Fields annotated with SkipJsonSchema will be excluded from the output.
        Only fields from AgentUpdate model are included.
        Deprecated fields with None or empty values are skipped.

        Returns:
            str: YAML representation of the agent with field descriptions as comments
        """
        data = {}
        yaml_lines = []

        def wrap_text(text: str, width: int = 80, prefix: str = "# ") -> list[str]:
            """Wrap text to specified width, preserving existing line breaks."""
            lines = []
            for paragraph in text.split("\\n"):
                if not paragraph:
                    lines.append(prefix.rstrip())
                    continue
                # Use textwrap to wrap each paragraph
                wrapped = textwrap.wrap(paragraph, width=width - len(prefix))
                lines.extend(prefix + line for line in wrapped)
            return lines

        # Get the field names from AgentUpdate model for filtering
        agent_update_fields = set(AgentUpdate.model_fields.keys())

        for field_name, field in type(self).model_fields.items():
            logger.debug("Processing field %s with type %s", field_name, field.metadata)
            # Skip fields that are not in AgentUpdate model
            if field_name not in agent_update_fields:
                continue

            # Skip fields with SkipJsonSchema annotation
            if any(type(item).__name__ == "SkipJsonSchema" for item in field.metadata):
                continue

            value = getattr(self, field_name)

            # Skip deprecated fields with None or empty values
            is_deprecated = hasattr(field, "deprecated") and field.deprecated
            if is_deprecated and not value:
                continue

            data[field_name] = value
            # Add comment from field description if available
            description = field.description
            if description:
                if len(yaml_lines) > 0:  # Add blank line between fields
                    yaml_lines.append("")
                # Split and wrap description into multiple lines
                yaml_lines.extend(wrap_text(description))

            # Check if the field is deprecated and add deprecation notice
            if is_deprecated:
                # Add deprecation message
                if hasattr(field, "deprecation_message") and field.deprecation_message:
                    yaml_lines.extend(
                        wrap_text(f"Deprecated: {field.deprecation_message}")
                    )
                else:
                    yaml_lines.append("# Deprecated")

            # Check if the field is experimental and add experimental notice
            if (
                hasattr(field, "json_schema_extra")
                and isinstance(field.json_schema_extra, dict)
                and field.json_schema_extra.get("x-group") == "experimental"
            ):
                yaml_lines.append("# Experimental")

            # Format the value based on its type
            if value is None:
                yaml_lines.append(f"{field_name}: null")
            elif isinstance(value, str):
                if "\\n" in value or len(value) > 60:
                    # Use block literal style (|) for multiline strings
                    # Remove any existing escaped newlines and use actual line breaks
                    value = value.replace("\\\\n", "\\n")
                    yaml_value = f"{field_name}: |-\\n"
                    # Indent each line with 2 spaces
                    yaml_value += "\\n".join(f"  {line}" for line in value.split("\\n"))
                    yaml_lines.append(yaml_value)
                else:
                    # Use flow style for short strings
                    yaml_value = yaml.dump(
                        {field_name: value},
                        default_flow_style=False,
                        allow_unicode=True,  # This ensures emojis are preserved
                    )
                    yaml_lines.append(yaml_value.rstrip())
            elif isinstance(value, list) and value and hasattr(value[0], "model_dump"):
                # Handle list of Pydantic models (e.g., list[AgentAutonomous])
                yaml_lines.append(f"{field_name}:")
                # Convert each Pydantic model to dict
                model_dicts = [
                    item.model_dump(exclude_none=True)
                    for item in value
                    if hasattr(item, "model_dump")
                ]
                # Dump the list of dicts
                yaml_value = yaml.dump(
                    model_dicts, default_flow_style=False, allow_unicode=True
                )
                # Indent all lines and append to yaml_lines
                indented_yaml = "\\n".join(
                    f"  {line}" for line in yaml_value.split("\\n")
                )
                yaml_lines.append(indented_yaml.rstrip())
            elif hasattr(value, "model_dump"):
                # Handle individual Pydantic model
                yaml_lines.append(f"{field_name}:")
                model_dump_func = getattr(value, "model_dump")
                yaml_value = yaml.dump(
                    model_dump_func(exclude_none=True),
                    default_flow_style=False,
                    allow_unicode=True,
                )
                # Indent all lines and append to yaml_lines
                indented_yaml = "\\n".join(
                    f"  {line}" for line in yaml_value.split("\\n") if line.strip()
                )
                yaml_lines.append(indented_yaml)
            else:
                # Handle Decimal and other types
                if isinstance(value, Decimal):
                    yaml_lines.append(f"{field_name}: {str(value)}")
                else:
                    yaml_value = yaml.dump(
                        {field_name: value},
                        default_flow_style=False,
                        allow_unicode=True,
                    )
                    yaml_lines.append(yaml_value.rstrip())

        return "\\n".join(yaml_lines) + "\\n"

    @staticmethod
    async def count() -> int:
        async with get_session() as db:
            result = await db.scalar(select(func.count(AgentTable.id)))
            return result or 0

    @classmethod
    async def get(cls, agent_id: str) -> "Agent | None":
        """Get agent by ID from database.

        .. deprecated::
            Use :func:`intentkit.core.agent.get_agent` instead.
            This method will be removed in a future version.
        """
        warnings.warn(
            "Agent.get() is deprecated, use intentkit.core.agent.get_agent() instead",
            DeprecationWarning,
            stacklevel=2,
        )
        async with get_session() as db:
            item = await db.scalar(select(AgentTable).where(AgentTable.id == agent_id))
            if item is None:
                return None
            return cls.model_validate(item)

    def skill_config(self, category: str) -> dict[str, Any]:
        return self.skills.get(category, {}) if self.skills else {}

    @staticmethod
    def _is_agent_owner_only_skill(skill_schema: dict[str, Any]) -> bool:
        """Check if a skill requires agent owner API keys only based on its resolved schema."""
        if (
            skill_schema
            and "properties" in skill_schema
            and "api_key_provider" in skill_schema["properties"]
        ):
            api_key_provider = skill_schema["properties"]["api_key_provider"]
            if "enum" in api_key_provider and api_key_provider["enum"] == [
                "agent_owner"
            ]:
                return True
        return False

    @classmethod
    async def get_json_schema(
        cls,
        db: AsyncSession,
        filter_owner_api_skills: bool = False,
    ) -> dict[str, Any]:
        """Get the JSON schema for Agent model with all $ref references resolved.

        This is the shared function that handles admin configuration filtering
        for both the API endpoint and agent generation.

        Args:
            db: Database session (optional, will create if not provided)
            filter_owner_api_skills: Whether to filter out skills that require agent owner API keys

        Returns:
            Dict containing the complete JSON schema for the Agent model
        """
        # Get the schema file path relative to this file
        current_dir = Path(__file__).parent
        agent_schema_path = current_dir / "schema.json"

        base_uri = f"file://{agent_schema_path}"
        with open(agent_schema_path) as f:
            schema: dict[str, Any] = jsonref.load(  # pyright: ignore[reportAssignmentType]
                f, base_uri=base_uri, proxies=False, lazy_load=False
            )

            # Get the model property from the schema
            model_property = schema.get("properties", {}).get("model", {})

            # Process model property using defaults merged with database overrides
            if model_property:
                new_enum = []

                for model_info in await LLMModelInfo.get_all(db):
                    if not model_info.enabled:
                        continue
                    new_enum.append(model_info.id)

                model_property["enum"] = new_enum

                if new_enum:
                    from intentkit.models.llm_picker import pick_default_model

                    try:
                        default_model = pick_default_model()
                    except RuntimeError:
                        default_model = new_enum[0]
                    current_default = model_property.get("default")
                    if not current_default or current_default not in new_enum:
                        if default_model in new_enum:
                            model_property["default"] = default_model
                        else:
                            model_property["default"] = new_enum[0]

            # Process skills property by scanning schema.json files directly
            skills_property = schema.get("properties", {}).get("skills", {})

            skills_properties = {}
            skills_dir = Path(__file__).parent.parent.parent / "skills"

            # Iterate over all skill category directories with schema.json
            if skills_dir.exists():
                for category_dir in sorted(skills_dir.iterdir()):
                    if not category_dir.is_dir():
                        continue
                    skill_schema_path = category_dir / "schema.json"
                    if not skill_schema_path.exists():
                        continue
                    category = category_dir.name
                    try:
                        with open(skill_schema_path) as f:
                            skill_schema = json.load(f)

                        # Check if this skill should be filtered for owner API requirements
                        if filter_owner_api_skills and cls._is_agent_owner_only_skill(
                            skill_schema
                        ):
                            logger.info(
                                f"Filtered out skill '{category}' from auto-generation: requires agent owner API key"
                            )
                            continue

                        # Load and embed the full skill schema directly
                        base_uri = f"file://{skill_schema_path}"
                        with open(skill_schema_path) as f:
                            embedded_skill_schema: dict[str, Any] = jsonref.load(  # pyright: ignore[reportAssignmentType]
                                f, base_uri=base_uri, proxies=False, lazy_load=False
                            )

                        skills_properties[category] = {
                            "title": skill_schema.get("title", category.title()),
                            **embedded_skill_schema,
                        }
                    except (FileNotFoundError, json.JSONDecodeError) as e:
                        logger.warning(
                            f"Could not load schema for skill category '{category}': {e}"
                        )
                        continue

            # Update the skills property in the schema
            if skills_property:
                skills_property["properties"] = skills_properties

            # Dynamically filter wallet_provider enum based on config
            wallet_property = schema.get("properties", {}).get("wallet_provider", {})
            if wallet_property:
                from intentkit.config.config import config

                wallet_enum = ["none", "native"]
                wallet_titles = ["None", "Native Wallet"]

                if (
                    config.cdp_api_key_id
                    and config.cdp_api_key_secret
                    and config.cdp_wallet_secret
                ):
                    wallet_enum.append("cdp")
                    wallet_titles.append("Coinbase Server Wallet V2")

                if config.privy_app_id and config.privy_app_secret:
                    wallet_enum.append("privy")
                    wallet_titles.append("Privy Wallet")

                    if config.master_wallet_private_key:
                        wallet_enum.append("safe")
                        wallet_titles.append("Safe Wallet")

                wallet_enum.append("readonly")
                wallet_titles.append("Readonly Wallet")

                wallet_property["enum"] = wallet_enum
                wallet_property["x-enum-title"] = wallet_titles

            # Log the changes for debugging
            logger.debug(
                "Schema processed with merged LLM/skill defaults; filtered owner API skills: %s",
                filter_owner_api_skills,
            )

            return schema
