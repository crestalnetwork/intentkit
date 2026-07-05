#!/usr/bin/env python3
"""Sync MCP server schemas — discovers tools and generates schema.json + __init__.py.

Usage:
    python scripts/sync_mcp_schemas.py

Requires the MCP server API keys to be set in environment variables.
"""

import asyncio
import json
import logging
from pathlib import Path

from intentkit.clients.mcp.client import list_mcp_tools
from intentkit.clients.mcp.registry import MCP_SERVERS, McpServerDef
from intentkit.config.config import config

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TOOLS_DIR = Path(__file__).parent.parent / "intentkit" / "tools"


def generate_schema(server_def: McpServerDef) -> dict:
    """Generate schema.json content for an MCP server tool category.

    The catalog is a fixed, coarse shape: one entry for the whole server
    (keyed by the server name), not a per-tool snapshot. The remote server's
    actual tools are discovered live at runtime, so the catalog never
    enumerates them and therefore never goes stale when the server changes.
    """
    schema: dict = {
        "title": server_def.display_name,
        "description": server_def.description,
        "x-tags": server_def.tags,
        "tools": {
            server_def.name: {
                "title": f"All {server_def.display_name} Tools",
                "description": (
                    f"Expose every tool offered by the {server_def.display_name} "
                    "MCP server. The exact tools are discovered live from the "
                    "server at runtime."
                ),
            }
        },
    }
    if server_def.web3:
        schema["x-web3"] = True
    return schema


def generate_init_py(server_name: str) -> str:
    """Generate __init__.py content for a thin tool category directory."""
    return f'''"""MCP: {MCP_SERVERS[server_name].display_name} tools (auto-generated)."""

from intentkit.tools.mcp.wrapper import create_mcp_category

_module = create_mcp_category("{server_name}")

get_tools = _module.get_tools
available = _module.available
'''


async def sync_server(server_def: McpServerDef) -> None:
    """Sync schema for a single MCP server.

    The generated schema is a fixed coarse shape derived only from the server
    definition, so syncing does not depend on the remote server. We still
    probe it for an informational tool count, but a failed probe does not fail
    the sync (the server may be down or its tool list may change later). A real
    failure (e.g. unwritable file) raises and aborts the run.
    """
    logger.info("Syncing '%s' from %s ...", server_def.name, server_def.url)

    # Resolve API key
    api_key = None
    if server_def.api_key_config_attr:
        api_key = getattr(config, server_def.api_key_config_attr, None)
        if not api_key:
            logger.warning(
                "  No API key found for '%s' (config.%s). Probing without auth...",
                server_def.name,
                server_def.api_key_config_attr,
            )

    # Informational connectivity probe only — not used to build the schema.
    try:
        tools = await list_mcp_tools(server_def, api_key)
        logger.info("  Reachable: server currently offers %d tool(s)", len(tools))
    except Exception:
        logger.warning(
            "  Could not reach '%s'; writing schema anyway (tools are "
            "discovered at runtime)",
            server_def.name,
        )

    # Create directory
    category_dir = TOOLS_DIR / server_def.name
    category_dir.mkdir(exist_ok=True)

    # Write schema.json (preserve x-icon from existing schema if present)
    schema = generate_schema(server_def)
    schema_path = category_dir / "schema.json"
    if schema_path.exists():
        existing = json.loads(schema_path.read_text())
        if "x-icon" in existing:
            schema["x-icon"] = existing["x-icon"]
    schema_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    logger.info("  Wrote %s", schema_path)

    # Write __init__.py (only if it doesn't exist or is auto-generated)
    init_path = category_dir / "__init__.py"
    if not init_path.exists() or "auto-generated" in init_path.read_text():
        init_path.write_text(generate_init_py(server_def.name))
        logger.info("  Wrote %s", init_path)
    else:
        logger.info("  Skipped %s (manually edited)", init_path)


async def main() -> None:
    """Sync all registered MCP servers."""
    logger.info("Syncing %d MCP server(s)...", len(MCP_SERVERS))
    for _name, server_def in MCP_SERVERS.items():
        await sync_server(server_def)
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
