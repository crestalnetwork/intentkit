#!/usr/bin/env python3
"""Scaffold toolset packages for registered MCP servers.

For each entry in MCP_SERVERS, creates intentkit/tools/<name>/ with the thin
auto-generated __init__.py wiring it to the MCP wrapper. All catalog metadata
(title, description, tags, web3, icon) comes from the McpServerDef itself at
runtime — nothing else needs to be generated. Drop an icon file into the
directory and set McpServerDef.icon to expose it.

Usage:
    python scripts/scaffold_mcp_tools.py
"""

import logging
from pathlib import Path

from intentkit.clients.mcp.registry import MCP_SERVERS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

TOOLS_DIR = Path(__file__).parent.parent / "intentkit" / "tools"


def generate_init_py(server_name: str) -> str:
    """Generate __init__.py content for a thin tool category directory."""
    return f'''"""MCP: {MCP_SERVERS[server_name].display_name} tools (auto-generated)."""

from intentkit.tools.mcp.wrapper import create_mcp_category

_module = create_mcp_category("{server_name}")

toolset = _module.toolset
get_tools = _module.get_tools
available = _module.available
'''


def main() -> None:
    logger.info("Scaffolding %d MCP server(s)...", len(MCP_SERVERS))
    for name in MCP_SERVERS:
        category_dir = TOOLS_DIR / name
        category_dir.mkdir(exist_ok=True)
        init_path = category_dir / "__init__.py"
        if not init_path.exists() or "auto-generated" in init_path.read_text():
            init_path.write_text(generate_init_py(name))
            logger.info("  Wrote %s", init_path)
        else:
            logger.info("  Skipped %s (manually edited)", init_path)
    logger.info("Done.")


if __name__ == "__main__":
    main()
