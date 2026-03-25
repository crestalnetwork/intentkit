# Skills Development Guide

This guide provides detailed information for developing skills in IntentKit.

## Overview

Skills are in the `intentkit/skills/` folder. Each folder is a category. Each skill category can contain multiple skills. A category can be a theme or a brand.

There are two ways to create a skill category:
1. **Native skills** — implement skills directly in Python (see [Skill Category Structure](#skill-category-structure))
2. **MCP-wrapped skills** — wrap a remote MCP server as a skill category with minimal code (see [MCP Skill Category Integration](#mcp-skill-category-integration))

## Dependency Rules

To avoid circular dependencies, Skills can only depend on the contents of models, abstracts, utils, and clients.

## Skill Category Structure

The necessary elements in a skill category folder are as follows. For the paradigm of each element, you can refer to existing skills, such as `skills/twitter`:

### 1. Base Class (`base.py`)

Base class inherit `IntentKitSkill`. If there are functions that are common to this category, they can also be written in BaseClass. A common example is `get_api_key`.

### 2. Individual Skill Files

Each skill should have its own file, with the same name as the skill. Key points:

- **Class Inheritance**: The skill class inherit BaseClass created in `base.py`

- **Name Attribute**: The `name` attribute needs a same prefix as the category name, such as `twitter_`, for uniqueness in the system.

- **Description Attribute**: The `description` attribute is the description of the skill, which will be used in LLM to select the skill.

- **Args Schema**: The `args_schema` attribute is the pydantic model for the skill arguments.

- **Main Logic (`_arun` method)**: The `_arun` method is the main logic of the skill.
  - There is special parameter `config: RunnableConfig`, which is used to pass the LangChain runnable config.
  - There is function `context_from_config` in IntentKitSkill, can be used to get the context from the runnable config.
  - In the `_arun` method, if there is any exception, just raise it, and the exception will be handled by the Agent.
  - If the return value is not a string, you can document it in the description attribute.

### 3. Initialization (`__init__.py`)

The `__init__.py` must have the function:
```python
async def get_skills(
    config: "Config",
    is_private: bool,
    **_,
) -> list[OpenAIBaseTool]
```

- **Config**: Config is inherit from `SkillConfig`, and the `states` is a dict, key is the skill name, value is the skill state. If the skill category have any other config fields need agent creator to set, they can be added to Config.

- **Caching**: If the skill is stateless, you can add a global `_cache` for it, to avoid re-create the skill object every time.

- **Availability Check**: The `__init__.py` must also have the function:
```python
def available() -> bool:
    """Check if this skill category is available based on system config."""
```
This function checks if all required system configuration variables exist. If the skill requires a platform-hosted API key (e.g., `config.tavily_api_key`), return whether that key is present. If the skill has no system config dependencies (e.g., only uses agent-owner provided keys), return `True`.


### 4. Visual Assets

A square image (icon/logo) is needed in the category folder. The `schema.json` must reference it via the `x-icon` field:
```json
"x-icon": "/skills/{category_name}/{icon_filename}.{ext}"
```
Supported formats: SVG, PNG, JPEG, WebP. Icons are served by the API at `GET /skills/{category}/{icon_name}.{ext}`.

### 5. Configuration Schema (`schema.json`)

Add `schema.json` file for the config, since the Config inherit from `SkillConfig`, you can check examples in exists skill category to find out the pattern.

The `x-tags` in schema should be in this list: AI, Analytics, Audio, Communication, Crypto, DeFi, Developer Tools, Entertainment, Identity, Image, Infrastructure, Knowledge Base, NFT, Search, Social

## Exception Handling

There is no need to catch exceptions in skills, because the agent has a dedicated module to catch skill exceptions. If you need to add more information to the exception, you can catch it and re-throw the appropriate exception.

---

## MCP Skill Category Integration

You can wrap any remote MCP (Model Context Protocol) server as an IntentKit skill category. The MCP framework handles tool discovery, schema generation, and runtime invocation automatically — you only need to register the server and run a sync script.

### Architecture

```
intentkit/clients/mcp/          # Shared MCP infrastructure
├── registry.py                 # Server definitions (McpServerDef)
├── client.py                   # HTTP client (SSE / Streamable HTTP transport)
├── wrapper.py                  # McpCategoryModule — provides get_skills/available/Config
└── tool.py                     # McpToolSkill — wraps individual MCP tools as IntentKit skills

intentkit/skills/mcp_{name}/    # Generated per-server skill category
├── __init__.py                 # Thin wrapper (auto-generated by sync script)
├── schema.json                 # Tool states + config (auto-generated by sync script)
└── {name}.{ext}                # Icon (manually added)

scripts/sync_mcp_schemas.py     # Discovers tools from live server → generates schema.json + __init__.py
```

### Step-by-Step: Adding a New MCP Server

#### 1. Add API key config (if needed)

If the MCP server requires an API key, add it to `intentkit/config/config.py`:
```python
self.my_service_api_key: str | None = self.load("MY_SERVICE_API_KEY")
```

#### 2. Register the server in `intentkit/clients/mcp/registry.py`

Add an entry to the `MCP_SERVERS` dict:
```python
"mcp_myservice": McpServerDef(
    name="mcp_myservice",               # Must match the dict key and skills/ folder name
    display_name="My Service",           # Human-readable name for UI
    description="What this service does",
    url="https://mcp.myservice.com/sse", # MCP server endpoint
    transport="sse",                     # "sse" or "streamable_http"
    api_key_config_attr="my_service_api_key",  # Attribute name in config.py (or None)
    api_key_header="Authorization",      # HTTP header for the key (or None)
    api_key_prefix="Bearer",             # Key prefix (or None for raw key)
    tags=["Developer Tools"],            # From the x-tags list above
),
```

Key fields:
- `name` — must be `mcp_{service}` and match the `MCP_SERVERS` dict key
- `transport` — `"sse"` for Server-Sent Events, `"streamable_http"` for HTTP streaming
- `api_key_config_attr` — set to `None` if the server needs no auth
- `api_key_prefix` — set to `None` to send the raw key without prefix

#### 3. Run the sync script

```bash
source .venv/bin/activate
python scripts/sync_mcp_schemas.py
```

This connects to the live MCP server, discovers all available tools, and generates:
- `intentkit/skills/mcp_myservice/__init__.py` — thin wrapper delegating to `McpCategoryModule`
- `intentkit/skills/mcp_myservice/schema.json` — tool states and config fields

The sync script preserves any manually added `x-icon` field in existing schema.json files.

#### 4. Add an icon

Download the service's official logo (square, SVG/PNG/JPEG/WebP) into the skill folder:
```
intentkit/skills/mcp_myservice/myservice.svg
```

Then add the `x-icon` field to `schema.json` (after `"title"`):
```json
"x-icon": "/skills/mcp_myservice/myservice.svg",
```

#### 5. Verify

- The skill category is auto-discovered by the executor via `importlib.import_module(f"intentkit.skills.{k}")` — no manual registration needed.
- The `available()` check returns `True` if no API key is required, or if the system-level key is configured.
- Agent owners can also provide per-agent API keys via the `api_key` field in skill config.

### How It Works at Runtime

1. **Discovery**: `McpCategoryModule.get_skills()` calls the MCP server to discover tools (cached for 1 hour).
2. **Filtering**: Only tools whose state is `"public"` or `"private"` (and matches `is_private`) are returned.
3. **Execution**: `McpToolSkill._arun()` calls `call_mcp_tool()` which opens an MCP session, invokes the tool, and returns the text result.
4. **API key resolution**: Per-agent key (from skill config) takes priority over the system key (from env/config).
