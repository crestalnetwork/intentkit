#!/usr/bin/env python3
"""Sync MCP server schemas — discovers tools and generates schema.json + __init__.py.

Usage:
    python scripts/sync_mcp_schemas.py

Requires the MCP server API keys to be set in environment variables.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

from intentkit.clients.mcp.client import McpToolInfo, list_mcp_tools
from intentkit.clients.mcp.registry import MCP_SERVERS, McpServerDef
from intentkit.config.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "intentkit" / "skills"


def generate_schema(server_def: McpServerDef, tools: list[McpToolInfo]) -> dict:
    """Generate schema.json content for an MCP server skill category."""
    states_properties: dict[str, object] = {}
    for tool in tools:
        skill_name = f"{server_def.name}_{tool.name}"
        states_properties[skill_name] = {
            "type": "string",
            "title": tool.name.replace("_", " ").title(),
            "description": tool.description or f"MCP tool: {tool.name}",
            "enum": ["disabled", "public", "private"],
            "x-enum-title": [
                "Disabled",
                "Agent Owner + All Users",
                "Agent Owner Only",
            ],
            "default": "disabled",
        }

    schema: dict[str, object] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": server_def.display_name,
        "description": server_def.description,
        "x-tags": server_def.tags,
        "properties": {
            "enabled": {
                "type": "boolean",
                "title": "Enabled",
                "default": False,
            },
            "states": {
                "type": "object",
                "title": "Skills",
                "properties": states_properties,
            },
        },
        "required": ["states", "enabled"],
        "additionalProperties": True,
    }

    # Add optional api_key field for per-agent key override
    if server_def.api_key_config_attr:
        props = schema["properties"]
        assert isinstance(props, dict)
        props["api_key"] = {
            "type": "string",
            "title": "API Key (optional, overrides system key)",
            "x-sensitive": True,
            "description": f"Your own API key for {server_def.display_name}. Leave empty to use the system key.",
        }

    return schema


def generate_init_py(server_name: str) -> str:
    """Generate __init__.py content for a thin skill category directory."""
    return f'''"""MCP: {MCP_SERVERS[server_name].display_name} skills (auto-generated)."""

from intentkit.clients.mcp.wrapper import create_mcp_category

_module = create_mcp_category("{server_name}")

get_skills = _module.get_skills
available = _module.available
Config = _module.Config
'''


async def sync_server(server_def: McpServerDef) -> bool:
    """Sync schema for a single MCP server. Returns True on success."""
    logger.info("Syncing '%s' from %s ...", server_def.name, server_def.url)

    # Resolve API key
    api_key = None
    if server_def.api_key_config_attr:
        api_key = getattr(config, server_def.api_key_config_attr, None)
        if not api_key:
            logger.warning(
                "  No API key found for '%s' (config.%s). Trying without auth...",
                server_def.name,
                server_def.api_key_config_attr,
            )

    try:
        tools = await list_mcp_tools(server_def, api_key)
    except Exception:
        logger.error("  Failed to connect to '%s'", server_def.name, exc_info=True)
        return False

    logger.info("  Discovered %d tools", len(tools))

    # Create directory
    category_dir = SKILLS_DIR / server_def.name
    category_dir.mkdir(exist_ok=True)

    # Write schema.json
    schema = generate_schema(server_def, tools)
    schema_path = category_dir / "schema.json"
    schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    logger.info("  Wrote %s", schema_path)

    # Write __init__.py (only if it doesn't exist or is auto-generated)
    init_path = category_dir / "__init__.py"
    if not init_path.exists() or "auto-generated" in init_path.read_text():
        init_path.write_text(generate_init_py(server_def.name))
        logger.info("  Wrote %s", init_path)
    else:
        logger.info("  Skipped %s (manually edited)", init_path)

    return True


async def main() -> None:
    """Sync all registered MCP servers."""
    logger.info("Syncing %d MCP server(s)...", len(MCP_SERVERS))

    results: dict[str, bool] = {}
    for name, server_def in MCP_SERVERS.items():
        results[name] = await sync_server(server_def)

    # Summary
    logger.info("")
    logger.info("=== Summary ===")
    for name, ok in results.items():
        status = "OK" if ok else "FAILED"
        logger.info("  %s: %s", name, status)

    failed = [n for n, ok in results.items() if not ok]
    if failed:
        logger.error("%d server(s) failed: %s", len(failed), ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
