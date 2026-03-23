"""McpToolSkill — wraps a single MCP tool as an IntentKit skill."""

import logging
from typing import Any

from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field, create_model

from intentkit.clients.mcp.client import McpToolError, call_mcp_tool
from intentkit.clients.mcp.registry import MCP_SERVERS, McpServerDef
from intentkit.config.config import config as system_config
from intentkit.skills.base import IntentKitSkill

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


class McpToolSkill(IntentKitSkill):
    """An IntentKit skill that wraps a single MCP tool."""

    category: str
    """Skill category name, e.g. 'mcp_coingecko'."""

    server_name: str
    """Registry key in MCP_SERVERS."""

    mcp_tool_name: str
    """Original tool name on the MCP server."""

    def _resolve_api_key(self, server_def: McpServerDef) -> str | None:
        """Resolve API key: agent skill config > system config."""
        try:
            context = self.get_context()
            skill_config = context.agent.skill_config(self.category)
            agent_key = skill_config.get("api_key") if skill_config else None
            if agent_key:
                return agent_key
        except ValueError:
            # No AgentContext available (e.g. during schema generation)
            pass
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


def create_mcp_skill(
    server_def: McpServerDef,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
) -> McpToolSkill:
    """Factory to create an McpToolSkill instance from MCP tool info."""
    args_model = create_args_model(tool_name, input_schema)
    # Prefix skill name with category to avoid name collisions
    skill_name = f"{server_def.name}_{tool_name}"

    return McpToolSkill(
        name=skill_name,
        description=tool_description or f"MCP tool: {tool_name}",
        args_schema=args_model,
        category=server_def.name,
        server_name=server_def.name,
        mcp_tool_name=tool_name,
    )
