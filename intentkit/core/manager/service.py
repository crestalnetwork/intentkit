"""Services for agent manager utilities."""

from __future__ import annotations

import json
import logging
from importlib import resources
from pathlib import Path
from typing import Any, cast

import jsonref
from fastapi import status

from intentkit.core.agent import get_agent
from intentkit.models.agent import AgentPublicInfo, AgentUserInput
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


def agent_draft_json_schema() -> dict[str, object]:
    """Return AgentUserInput schema tailored for LLM draft generation."""
    schema: dict[str, Any] = AgentUserInput.model_json_schema()
    properties: dict[str, object] = schema.get("properties", {})

    fields_to_remove = {"autonomous", "frequency_penalty", "presence_penalty"}
    for field in fields_to_remove:
        _ = properties.pop(field, None)

    if "required" in schema and isinstance(schema["required"], list):
        schema["required"] = [
            field for field in schema["required"] if field not in fields_to_remove
        ]

    skills_property = properties.get("skills")
    if not isinstance(skills_property, dict):
        return schema

    skills_property = cast(dict[str, Any], skills_property)

    skills_properties: dict[str, object] = {}
    try:
        traversable = resources.files("intentkit.skills")
        with resources.as_file(traversable) as skills_root:
            for entry in skills_root.iterdir():
                if not entry.is_dir():
                    continue

                schema_path = entry / "schema.json"
                if not schema_path.is_file():
                    continue

                try:
                    skills_properties[entry.name] = _load_skill_schema(schema_path)
                except (
                    OSError,
                    ValueError,
                    json.JSONDecodeError,
                    jsonref.JsonRefError,
                ) as exc:
                    logger.warning(
                        "Failed to load schema for skill '%s': %s", entry.name, exc
                    )
                    continue
    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning("intentkit skills package not found when building schema")
        return schema

    if skills_properties:
        _ = skills_property.setdefault("type", "object")
        skills_property["properties"] = skills_properties

    return schema


def get_skills_hierarchical_text() -> str:
    """Extract skills organized by category and return as hierarchical text."""
    try:
        traversable = resources.files("intentkit.skills")
        with resources.as_file(traversable) as skills_root:
            # Group skills by category (x-tags)
            categories: dict[str, list[Any]] = {}
            for entry in skills_root.iterdir():
                if not entry.is_dir():
                    continue

                schema_path = entry / "schema.json"
                if not schema_path.is_file():
                    continue

                try:
                    skill_schema = _load_skill_schema(schema_path)
                    skill_name = entry.name
                    skill_title = skill_schema.get(
                        "title", skill_name.replace("_", " ").title()
                    )
                    skill_description = skill_schema.get(
                        "description", "No description available"
                    )
                    skill_tags = cast(list[str], skill_schema.get("x-tags", ["Other"]))

                    # Use the first tag as the primary category
                    primary_category = skill_tags[0] if skill_tags else "Other"

                    if primary_category not in categories:
                        categories[primary_category] = []

                    # Extract individual skills from states.properties
                    individual_skills: list[dict[str, str]] = []
                    states_props = _get_states_properties(skill_schema)
                    if states_props:
                        for ind_name, ind_def in states_props.items():
                            ind_desc = (
                                ind_def.get("description", "No description available")
                                if isinstance(ind_def, dict)
                                else "No description available"
                            )
                            individual_skills.append(
                                {"name": ind_name, "description": ind_desc}
                            )

                    categories[primary_category].append(
                        {
                            "name": skill_name,
                            "title": skill_title,
                            "description": skill_description,
                            "individual_skills": individual_skills,
                        }
                    )

                except (
                    OSError,
                    ValueError,
                    json.JSONDecodeError,
                    jsonref.JsonRefError,
                ) as exc:
                    logger.warning(
                        "Failed to load schema for skill '%s': %s", entry.name, exc
                    )
                    continue
    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning("intentkit skills package not found when building skills text")
        return "No skills available"

    # Build hierarchical text
    text_lines = []
    text_lines.append("Available Skills by Category:")
    text_lines.append("")

    # Sort categories alphabetically
    for category in sorted(categories.keys()):
        text_lines.append(f"#### {category}")
        text_lines.append("")

        # Sort skills within category alphabetically by name
        for skill in sorted(categories[category], key=lambda x: x["name"]):
            text_lines.append(
                f"- **{skill['name']}** ({skill['title']}): {skill['description']}"
            )
            # Add individual skills indented under the category skill
            for ind_skill in sorted(
                skill.get("individual_skills", []), key=lambda x: x["name"]
            ):
                text_lines.append(
                    f"  - `{ind_skill['name']}`: {ind_skill['description']}"
                )

        text_lines.append("")

    return "\n".join(text_lines)


def _load_skill_schema(schema_path: Path) -> dict[str, object]:
    base_uri = f"file://{schema_path}"
    with schema_path.open("r", encoding="utf-8") as schema_file:
        embedded_schema: dict[str, object] = cast(
            dict[str, object],
            jsonref.load(
                schema_file, base_uri=base_uri, proxies=False, lazy_load=False
            ),
        )

    schema_copy = dict(embedded_schema)
    _ = schema_copy.setdefault(
        "title", schema_path.parent.name.replace("_", " ").title()
    )
    return schema_copy


def _get_states_properties(skill_schema: dict[str, object]) -> dict[str, Any] | None:
    """Extract states.properties from a skill schema, or None if invalid."""
    properties = skill_schema.get("properties", {})
    if not isinstance(properties, dict):
        return None
    states = properties.get("states", {})
    if not isinstance(states, dict):
        return None
    state_props = states.get("properties", {})
    return cast(dict[str, Any], state_props) if isinstance(state_props, dict) else None


def get_valid_skills_registry() -> dict[str, dict[str, str]]:
    """Load all skill schemas and return a registry of valid skills.

    Returns a nested dict mapping category name to a dict of skill names
    and their descriptions: ``{category: {skill_name: description}}``.

    Broken or unreadable schemas are silently skipped.
    """
    registry: dict[str, dict[str, str]] = {}
    try:
        traversable = resources.files("intentkit.skills")
        with resources.as_file(traversable) as skills_root:
            for entry in sorted(skills_root.iterdir(), key=lambda p: p.name):
                if not entry.is_dir():
                    continue

                schema_path = entry / "schema.json"
                if not schema_path.is_file():
                    continue

                try:
                    skill_schema = _load_skill_schema(schema_path)
                except (
                    OSError,
                    ValueError,
                    json.JSONDecodeError,
                    jsonref.JsonRefError,
                ) as exc:
                    logger.warning(
                        "Failed to load schema for skill '%s': %s", entry.name, exc
                    )
                    continue

                state_props = _get_states_properties(skill_schema)
                if not state_props:
                    continue

                category_name = entry.name
                skills: dict[str, str] = {}
                for skill_name, skill_def in state_props.items():
                    if isinstance(skill_def, dict):
                        description = skill_def.get("description", "")
                        if isinstance(description, str) and description:
                            skills[skill_name] = description

                if skills:
                    registry[category_name] = skills

    except (AttributeError, ModuleNotFoundError, ImportError):
        logger.warning(
            "intentkit skills package not found when building skills registry"
        )

    return registry


_VALID_SKILL_STATES = {"disabled", "public", "private"}


def validate_skills(skills: dict[str, Any] | None) -> None:
    """Validate skills config. Raises IntentKitAPIError(400) on invalid entries."""
    if not skills:
        return

    registry = get_valid_skills_registry()
    valid_categories = sorted(registry.keys())

    for category, config in skills.items():
        if category not in registry:
            raise IntentKitAPIError(
                400,
                "InvalidSkillCategory",
                f"Unknown skill category '{category}'. Valid categories: {valid_categories}",
            )

        if not isinstance(config, dict):
            raise IntentKitAPIError(
                400,
                "InvalidSkillFormat",
                f"Skill category '{category}' config must be a dict, got {type(config).__name__}",
            )

        states = config.get("states")
        if states is not None and not isinstance(states, dict):
            raise IntentKitAPIError(
                400,
                "InvalidSkillFormat",
                f"'states' in category '{category}' must be a dict, got {type(states).__name__}",
            )

        if not isinstance(states, dict):
            states = {}
        valid_skill_names = sorted(registry[category].keys())

        for skill_name, state_value in states.items():
            if skill_name not in registry[category]:
                raise IntentKitAPIError(
                    400,
                    "InvalidSkillName",
                    f"Unknown skill '{skill_name}' in category '{category}'. Valid skills: {valid_skill_names}",
                )
            if state_value not in _VALID_SKILL_STATES:
                raise IntentKitAPIError(
                    400,
                    "InvalidSkillState",
                    f"Invalid state '{state_value}' for skill '{skill_name}'. Valid states: {sorted(_VALID_SKILL_STATES)}",
                )


def sanitize_skills(skills: dict[str, Any] | None) -> dict[str, Any] | None:
    """Remove skills/categories not in schema. Returns cleaned dict or None if empty."""
    if not skills:
        return None

    registry = get_valid_skills_registry()
    cleaned: dict[str, Any] = {}

    for category, config in skills.items():
        if category not in registry:
            continue

        # Preserve non-dict configs as-is (don't silently drop)
        if not isinstance(config, dict):
            cleaned[category] = config
            continue

        states = config.get("states")
        # Preserve non-dict states as-is
        if not isinstance(states, dict):
            cleaned[category] = config
            continue

        cleaned_states = {
            skill_name: state_value
            for skill_name, state_value in states.items()
            if skill_name in registry[category]
        }

        if cleaned_states:
            cleaned_config = dict(config)
            cleaned_config["states"] = cleaned_states
            cleaned[category] = cleaned_config

    return cleaned if cleaned else None


async def get_latest_public_info(*, agent_id: str, user_id: str) -> AgentPublicInfo:
    """Return the latest public information for a specific agent."""

    agent = await get_agent(agent_id)
    if not agent:
        raise IntentKitAPIError(
            status.HTTP_404_NOT_FOUND, "AgentNotFound", "Agent not found"
        )

    if agent.owner != user_id:
        raise IntentKitAPIError(
            status.HTTP_403_FORBIDDEN,
            "AgentForbidden",
            "Not authorized to access this agent",
        )

    return AgentPublicInfo.model_validate(agent)
