"""McpToolTool — wraps a single MCP tool as an IntentKit tool.

Lives in the tools layer (not clients) because it depends on
``intentkit.tools.base``; the protocol-level MCP client stays in
``intentkit.clients.mcp``.
"""

import logging
from typing import Any

from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field, create_model

from intentkit.clients.mcp.client import McpToolError, call_mcp_tool
from intentkit.clients.mcp.registry import MCP_SERVERS, McpServerDef
from intentkit.config.config import config as system_config
from intentkit.tools.base import IntentKitTool

logger = logging.getLogger(__name__)

# JSON Schema type to Python type mapping
_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _json_schema_to_python_type(prop_schema: dict[str, Any]) -> type:
    """Convert a JSON Schema property to a Python type."""
    json_type = prop_schema.get("type", "string")
    if json_type == "array":
        items_type = _json_schema_to_python_type(prop_schema.get("items", {}))
        return list[items_type]  # type: ignore[valid-type]
    if json_type == "object":
        return dict[str, Any]
    return _JSON_TYPE_MAP.get(json_type, str)


def create_args_model(tool_name: str, input_schema: dict[str, Any]) -> type[BaseModel]:
    """Create a Pydantic model from an MCP tool's inputSchema."""
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    if not properties:
        # No properties — return a no-args model
        return create_model(f"{tool_name}_args")  # type: ignore[call-overload]

    fields: dict[str, Any] = {}
    for prop_name, prop_schema in properties.items():
        python_type = _json_schema_to_python_type(prop_schema)
        description = prop_schema.get("description", "")
        default = prop_schema.get("default")

        if prop_name in required:
            fields[prop_name] = (
                python_type,
                Field(description=description),
            )
        else:
            fields[prop_name] = (
                python_type | None,
                Field(default=default, description=description),
            )

    return create_model(f"{tool_name}_args", **fields)  # type: ignore[call-overload]


class McpToolTool(IntentKitTool):
    """An IntentKit tool that wraps a single MCP tool."""

    category: str
    """Toolset name, e.g. 'mcp_coingecko'."""

    server_name: str
    """Registry key in MCP_SERVERS."""

    mcp_tool_name: str
    """Original tool name on the MCP server."""

    def _resolve_api_key(self, server_def: McpServerDef) -> str | None:
        """Resolve the platform-level API key for the server, if any."""
        if server_def.api_key_config_attr:
            return getattr(system_config, server_def.api_key_config_attr, None)
        return None

    async def _arun(self, **kwargs: Any) -> str:
        server_def = MCP_SERVERS.get(self.server_name)
        if not server_def:
            raise ToolException(
                f"MCP server '{self.server_name}' not found in registry"
            )

        api_key = self._resolve_api_key(server_def)
        try:
            return await call_mcp_tool(server_def, api_key, self.mcp_tool_name, kwargs)
        except McpToolError as e:
            raise ToolException(str(e)) from e
        except Exception as e:
            raise ToolException(
                f"Failed to call MCP tool '{self.mcp_tool_name}': {e}"
            ) from e


def create_mcp_tool(
    server_def: McpServerDef,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
) -> McpToolTool:
    """Factory to create an McpToolTool instance from MCP tool info."""
    args_model = create_args_model(tool_name, input_schema)
    # The LangChain-facing name is prefixed with the category to avoid
    # collisions, but the remote server only knows the original name.
    prefixed_name = f"{server_def.name}_{tool_name}"

    return McpToolTool(
        name=prefixed_name,
        description=tool_description or f"MCP tool: {prefixed_name}",
        args_schema=args_model,
        category=server_def.name,
        server_name=server_def.name,
        mcp_tool_name=tool_name,
    )
