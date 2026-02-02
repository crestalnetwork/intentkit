from __future__ import annotations

import json
import logging
import re
import textwrap
import warnings
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import jsonref
import yaml
from pydantic import ConfigDict
from pydantic import Field as PydanticField
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.agent.autonomous import AgentAutonomous
from intentkit.models.agent.base import AgentPublicInfo
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent.user_input import AgentCreate, AgentUpdate
from intentkit.models.credit import CreditAccount
from intentkit.models.llm import LLMModelInfo, LLMProvider
from intentkit.models.skill import Skill
from intentkit.utils.ens import resolve_ens_to_address
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)

ENS_NAME_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:eth|base\.eth)$",
    re.IGNORECASE,
)


class Agent(AgentCreate, AgentPublicInfo):
    """Agent model."""

    model_config = ConfigDict(from_attributes=True)

    slug: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Slug of the agent, used for URL generation",
            max_length=100,
            min_length=2,
        ),
    ]
    version: Annotated[
        str | None,
        PydanticField(
            default=None,
            description="Version hash of the agent",
        ),
    ]
    statistics: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Statistics of the agent, update every 1 hour for query",
        ),
    ]
    assets: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Assets of the agent, update every 1 hour for query",
        ),
    ]
    account_snapshot: Annotated[
        CreditAccount | None,
        PydanticField(
            default=None,
            description="Account snapshot of the agent, update every 1 hour for query",
        ),
    ]
    extra: Annotated[
        dict[str, Any] | None,
        PydanticField(
            default=None,
            description="Other helper data fields for query, come from agent and agent data",
        ),
    ]
    deployed_at: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Timestamp when the agent was deployed",
        ),
    ]
    public_info_updated_at: Annotated[
        datetime | None,
        PydanticField(
            default=None,
            description="Timestamp when the agent public info was last updated",
        ),
    ]
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

    def has_search(self) -> bool:
        texts = [
            self.prompt,
            self.prompt_append,
            self.purpose,
            self.personality,
            self.principles,
        ]
        for t in texts:
            if t and (re.search(r"@search\\b", t) or re.search(r"@web\\b", t)):
                return True
        return False

    def has_super(self) -> bool:
        texts = [
            self.prompt,
            self.prompt_append,
            self.purpose,
            self.personality,
            self.principles,
        ]
        for t in texts:
            if t and re.search(r"@super\\b", t):
                return True
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
            logger.debug(f"Processing field {field_name} with type {field.metadata}")
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

    @classmethod
    async def get_by_id_or_slug(cls, agent_id: str) -> "Agent | None":
        """Get agent by ID or slug.

        First tries to get by ID if agent_id length <= 20,
        then falls back to searching by slug if not found.

        Args:
            agent_id: Agent ID or slug to search for

        Returns:
            Agent if found, None otherwise
        """
        query_id = agent_id
        if ENS_NAME_PATTERN.fullmatch(agent_id):
            query_id = await resolve_ens_to_address(agent_id)

        async with get_session() as db:
            agent = None

            # Try to get by ID if length <= 20
            if len(query_id) <= 20 or query_id.startswith("0x"):
                agent = await Agent.get(query_id)

            # If not found, try to get by slug
            if agent is None:
                slug_stmt = select(AgentTable).where(AgentTable.slug == query_id)
                agent_row = await db.scalar(slug_stmt)
                if agent_row is not None:
                    agent = Agent.model_validate(agent_row)

            return agent

    @staticmethod
    def _deserialize_autonomous(
        autonomous_data: list[Any] | None,
    ) -> list[AgentAutonomous]:
        if not autonomous_data:
            return []

        deserialized: list[AgentAutonomous] = []
        for entry in autonomous_data:
            if isinstance(entry, AgentAutonomous):
                deserialized.append(entry)
            else:
                deserialized.append(AgentAutonomous.model_validate(entry))
        return deserialized

    @staticmethod
    def _serialize_autonomous(tasks: list[AgentAutonomous]) -> list[dict[str, Any]]:
        return [task.model_dump(mode="json") for task in tasks]

    @staticmethod
    def _autonomous_not_allowed_error() -> IntentKitAPIError:
        return IntentKitAPIError(
            400,
            "AgentNotDeployed",
            "Only deployed agents can call this feature.",
        )

    async def list_autonomous_tasks(self) -> list[AgentAutonomous]:
        persisted = await Agent.get(self.id)
        if persisted is None:
            raise self._autonomous_not_allowed_error()

        tasks = persisted.autonomous or []
        # Keep local state in sync with persisted data
        self.autonomous = tasks
        return tasks

    async def add_autonomous_task(self, task: AgentAutonomous) -> AgentAutonomous:
        async with get_session() as session:
            db_agent = await session.get(AgentTable, self.id)
            if db_agent is None:
                raise self._autonomous_not_allowed_error()

            current_tasks = self._deserialize_autonomous(db_agent.autonomous)
            normalized_task = task.normalize_status_defaults()
            current_tasks.append(normalized_task)

            db_agent.autonomous = self._serialize_autonomous(current_tasks)
            await session.commit()

        self.autonomous = current_tasks
        return normalized_task

    async def delete_autonomous_task(self, task_id: str) -> None:
        async with get_session() as session:
            db_agent = await session.get(AgentTable, self.id)
            if db_agent is None:
                raise self._autonomous_not_allowed_error()

            current_tasks = self._deserialize_autonomous(db_agent.autonomous)

            updated_tasks = [task for task in current_tasks if task.id != task_id]
            if len(updated_tasks) == len(current_tasks):
                raise IntentKitAPIError(
                    404,
                    "TaskNotFound",
                    f"Autonomous task with ID {task_id} not found.",
                )

            db_agent.autonomous = self._serialize_autonomous(updated_tasks)
            await session.commit()

        self.autonomous = updated_tasks

    async def update_autonomous_task(
        self, task_id: str, task_updates: dict[str, Any]
    ) -> AgentAutonomous:
        async with get_session() as session:
            db_agent = await session.get(AgentTable, self.id)
            if db_agent is None:
                raise self._autonomous_not_allowed_error()

            current_tasks = self._deserialize_autonomous(db_agent.autonomous)

            updated_task: AgentAutonomous | None = None
            rewritten_tasks: list[AgentAutonomous] = []
            for task in current_tasks:
                if task.id == task_id:
                    task_dict = task.model_dump()
                    task_dict.update(task_updates)
                    updated_task = AgentAutonomous.model_validate(
                        task_dict
                    ).normalize_status_defaults()
                    rewritten_tasks.append(updated_task)
                else:
                    rewritten_tasks.append(task)

            if updated_task is None:
                raise IntentKitAPIError(
                    404,
                    "TaskNotFound",
                    f"Autonomous task with ID {task_id} not found.",
                )

            db_agent.autonomous = self._serialize_autonomous(rewritten_tasks)
            await session.commit()

        self.autonomous = rewritten_tasks
        return updated_task

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
        current_dir = Path(__file__).parent.parent
        agent_schema_path = current_dir / "agent_schema.json"

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
                new_enum_title = []
                new_enum_category = []
                new_enum_support_skill = []

                for model_info in await LLMModelInfo.get_all(db):
                    if not model_info.enabled:
                        continue

                    provider = (
                        LLMProvider(model_info.provider)
                        if isinstance(model_info.provider, str)
                        else model_info.provider
                    )

                    new_enum.append(model_info.id)
                    new_enum_title.append(model_info.name)
                    new_enum_category.append(provider.display_name())
                    new_enum_support_skill.append(model_info.supports_skill_calls)

                model_property["enum"] = new_enum
                model_property["x-enum-title"] = new_enum_title
                model_property["x-enum-category"] = new_enum_category
                model_property["x-support-skill"] = new_enum_support_skill

                if (
                    "default" in model_property
                    and model_property["default"] not in new_enum
                    and new_enum
                ):
                    model_property["default"] = new_enum[0]

            # Process skills property using data from Skill.get_all instead of agent_schema.json
            skills_property = schema.get("properties", {}).get("skills", {})

            # Build skill_states_map from database
            skill_states_map: dict[str, dict[str, Skill]] = {}
            for skill_model in await Skill.get_all(db):
                if not skill_model.config_name:
                    continue
                category_states = skill_states_map.setdefault(skill_model.category, {})
                if skill_model.enabled:
                    category_states[skill_model.config_name] = skill_model
                else:
                    category_states.pop(skill_model.config_name, None)

            enabled_categories = {
                category for category, states in skill_states_map.items() if states
            }

            # Calculate price levels and skills data
            category_avg_price_levels = {}
            skills_data = {}
            for category, states in skill_states_map.items():
                if not states:
                    continue
                price_levels = [
                    state.price_level
                    for state in states.values()
                    if state.price_level is not None
                ]
                if price_levels:
                    category_avg_price_levels[category] = int(
                        sum(price_levels) / len(price_levels)
                    )
                skills_data[category] = {
                    config_name: state.price_level
                    for config_name, state in states.items()
                }

            # Dynamically generate skills_properties from Skill.get_all data
            skills_properties = {}
            current_dir = Path(__file__).parent.parent.parent

            for category in enabled_categories:
                # Skip if filtered for auto-generation
                skill_schema_path = current_dir / "skills" / category / "schema.json"
                if skill_schema_path.exists():
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

                        # Create skill property with embedded schema instead of reference
                        # Load and embed the full skill schema directly
                        base_uri = f"file://{skill_schema_path}"
                        with open(skill_schema_path) as f:
                            embedded_skill_schema: dict[str, Any] = jsonref.load(  # pyright: ignore[reportAssignmentType]
                                f, base_uri=base_uri, proxies=False, lazy_load=False
                            )

                        skills_properties[category] = {
                            "title": skill_schema.get("title", category.title()),
                            **embedded_skill_schema,  # Embed the full schema instead of using $ref
                        }

                        # Add price level information
                        if category in category_avg_price_levels:
                            skills_properties[category]["x-avg-price-level"] = (
                                category_avg_price_levels[category]
                            )

                        if category in skills_data:
                            # Add price level to states in the embedded schema
                            skill_states = (
                                skills_properties[category]
                                .get("properties", {})
                                .get("states", {})
                                .get("properties", {})
                            )
                            for state_name, state_config in skill_states.items():
                                if (
                                    state_name in skills_data[category]
                                    and skills_data[category][state_name] is not None
                                ):
                                    state_config["x-price-level"] = skills_data[
                                        category
                                    ][state_name]
                    except (FileNotFoundError, json.JSONDecodeError) as e:
                        logger.warning(
                            f"Could not load schema for skill category '{category}': {e}"
                        )
                        continue

            # Update the skills property in the schema
            if skills_property:
                skills_property["properties"] = skills_properties

            # Log the changes for debugging
            logger.debug(
                "Schema processed with merged LLM/skill defaults; filtered owner API skills: %s",
                filter_owner_api_skills,
            )

            return schema
