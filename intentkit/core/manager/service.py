"""Services for agent manager utilities."""

from __future__ import annotations

import json
import logging
from importlib import resources
from pathlib import Path
from typing import Any

import jsonref
from fastapi import status

from intentkit.core.agent import get_agent
from intentkit.models.agent import AgentPublicInfo, AgentUserInput
from intentkit.utils.error import IntentKitAPIError

logger = logging.getLogger(__name__)


def agent_draft_json_schema() -> dict[str, object]:
    """Return AgentUserInput schema tailored for LLM draft generation."""
    schema: dict[str, object] = AgentUserInput.model_json_schema()
    properties: dict[str, object] = schema.get("properties", {})

    fields_to_remove = {"autonomous", "frequency_penalty", "presence_penalty"}
    for field in fields_to_remove:
        properties.pop(field, None)

    if "required" in schema and isinstance(schema["required"], list):
        schema["required"] = [
            field for field in schema["required"] if field not in fields_to_remove
        ]

    skills_property = properties.get("skills")
    if not isinstance(skills_property, dict):
        return schema

    skills_properties: dict[str, object] = {}
    try:
        skills_root = resources.files("intentkit.skills")
    except (AttributeError, ModuleNotFoundError):
        logger.warning("intentkit skills package not found when building schema")
        return schema

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
            logger.warning("Failed to load schema for skill '%s': %s", entry.name, exc)
            continue

    if skills_properties:
        skills_property.setdefault("type", "object")
        skills_property["properties"] = skills_properties

    return schema


def get_skills_hierarchical_text() -> str:
    """Extract skills organized by category and return as hierarchical text."""
    try:
        skills_root = resources.files("intentkit.skills")
    except (AttributeError, ModuleNotFoundError):
        logger.warning("intentkit skills package not found when building skills text")
        return "No skills available"

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
            skill_tags = skill_schema.get("x-tags", ["Other"])

            # Use the first tag as the primary category
            primary_category = skill_tags[0] if skill_tags else "Other"

            if primary_category not in categories:
                categories[primary_category] = []

            categories[primary_category].append(
                {
                    "name": skill_name,
                    "title": skill_title,
                    "description": skill_description,
                }
            )

        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
            jsonref.JsonRefError,
        ) as exc:
            logger.warning("Failed to load schema for skill '%s': %s", entry.name, exc)
            continue

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

        text_lines.append("")

    return "\n".join(text_lines)


def _load_skill_schema(schema_path: Path) -> dict[str, object]:
    base_uri = f"file://{schema_path}"
    with schema_path.open("r", encoding="utf-8") as schema_file:
        embedded_schema: dict[str, object] = jsonref.load(
            schema_file, base_uri=base_uri, proxies=False, lazy_load=False
        )

    schema_copy = dict(embedded_schema)
    schema_copy.setdefault("title", schema_path.parent.name.replace("_", " ").title())
    return schema_copy


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
