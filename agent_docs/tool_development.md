# Tools Development Guide

This guide provides detailed information for developing tools in IntentKit.

## Overview

Tools are in the `intentkit/tools/` folder. Each folder is a category. Each tool category can contain multiple tools. A category can be a theme or a brand.

There are two ways to create a tool category:
1. **Native tools** — implement tools directly in Python (see [Tool Category Structure](#tool-category-structure))
2. **MCP-wrapped tools** — wrap a remote MCP server as a tool category with minimal code (see [MCP Tool Category Integration](#mcp-tool-category-integration))

## Dependency Rules

To avoid circular dependencies, Tools can only depend on the contents of models, abstracts, utils, and clients.

## Tool Category Structure

The necessary elements in a tool category folder are as follows. For the paradigm of each element, you can refer to existing tools, such as `tools/firecrawl`:

### 1. Base Class (`base.py`)

Base class inherit `IntentKitTool`. If there are functions that are common to this category, they can also be written in BaseClass. A common example is `get_api_key`.

### 2. Individual Tool Files

Each tool should have its own file, with the same name as the tool. Key points:

- **Class Inheritance**: The tool class inherit BaseClass created in `base.py`

- **Name Attribute**: The `name` attribute needs a same prefix as the category name, such as `firecrawl_`, for uniqueness in the system.

- **Description Attribute**: The `description` attribute is the description of the tool, which will be used in LLM to select the tool.

- **Args Schema**: The `args_schema` attribute is the pydantic model for the tool arguments.

- **Main Logic (`_arun` method)**: The `_arun` method is the main logic of the tool.
  - There is special parameter `config: RunnableConfig`, which is used to pass the LangChain runnable config.
  - There is function `context_from_config` in IntentKitTool, can be used to get the context from the runnable config.
  - In the `_arun` method, if there is any exception, just raise it, and the exception will be handled by the Agent.
  - If the return value is not a string, you can document it in the description attribute.

### 3. Initialization (`__init__.py`)

The `__init__.py` must have the function:
```python
async def get_tools(
    tool_names: list[str],
    **_,
) -> list[BaseTool]
```

- **tool_names**: The subset of this category's tool names the agent enabled
  (the agent config is a flat list of tool names; the executor groups it by
  category). Return instances for the requested names; skip unknown names.
  Tool names must equal the instance's `name` attribute and be globally
  unique (category-prefixed, e.g. `firecrawl_scrape`).

- **Caching**: If the tool is stateless, you can add a global `_cache` for it, to avoid re-create the tool object every time.

- **Availability Check**: The `__init__.py` must also have the function:
```python
def available() -> bool:
    """Check if this tool category is available based on system config."""
```
This function checks if all required system configuration variables exist. If the tool requires a platform-hosted API key (e.g., `config.tavily_api_key`), return whether that key is present. If the tool has no system config dependencies (e.g., only uses agent-owner provided keys), return `True`.


### 4. Visual Assets

A square image (icon/logo) is needed in the category folder. Reference it via
the `icon` field of the toolset metadata (see below):
```python
icon="/tools/{category_name}/{icon_filename}.{ext}"
```
Supported formats: SVG, PNG, JPEG, WebP. Icons are served by the API at `GET /tools/{category}/{icon_name}.{ext}`.

### 5. Catalog Metadata (in code)

The catalog is derived from the code — there is no schema file:

- **Category level**: declare a module-level `toolset` in `__init__.py`:

```python
from intentkit.tools.meta import ToolsetMeta

toolset = ToolsetMeta(
    title="My Category",
    description="...",
    tags=["..."],
    icon="/tools/my_category/icon.png",
)
```

- **Tool level**: each tool class declares `title` (display name for pickers)
  next to its `name`; the `description` doubles as the catalog description:

```python
class MyTool(MyCategoryBaseTool):
    name: str = "my_category_tool_name"
    title: str = "My Tool"
    description: str = "..."
```

The registry (`intentkit/core/agent/tool_registry.py`) discovers every package
that declares a `toolset` meta and collects its `IntentKitTool` subclasses;
frontend pickers and validation are built from that. A tool class that is not
wired into the module's `get_tools` name map fails
`tests/tools/test_catalog_sync.py`.

### Web3 tool categories

Categories whose tools operate on team wallets must set `web3=True` in their
`ToolsetMeta`. Consequences:

- They are only selectable for agents whose team owns at least one wallet
  (enforced at agent create/update, hidden in pickers otherwise).
- The team's wallets are listed in the agent's system prompt.
- Every wallet-using tool takes a `wallet_address` argument (use
  `WALLET_ADDRESS_ARG_DESCRIPTION` from `intentkit.tools.onchain`); the agent
  picks the wallet per call.
- Read-only usage resolves the wallet with `self.resolve_wallet(address)` and
  reads via `self.web3_client()`. Anything that signs or sends must use the
  guarded helpers (`get_unified_wallet` / `get_wallet_provider` /
  `get_wallet_signer` / `get_evm_account`), which refuse to sign unless the
  owning team is running the agent (`context.is_own_team`).

The `tags` in the toolset metadata should be in this list: AI, Analytics, Audio, Communication, Crypto, DeFi, Developer Tools, Entertainment, Identity, Image, Infrastructure, Knowledge Base, NFT, Search, Social

## Exception Handling

There is no need to catch exceptions in tools, because the agent has a dedicated module to catch tool exceptions. If you need to add more information to the exception, you can catch it and re-throw the appropriate exception.

---

## MCP Tool Category Integration

You can wrap any remote MCP (Model Context Protocol) server as an IntentKit tool category. The MCP framework handles tool discovery, schema generation, and runtime invocation automatically — you only need to register the server and run a sync script.

### Architecture

```
intentkit/clients/mcp/          # MCP protocol client (clients layer)
├── registry.py                 # Server definitions (McpServerDef)
└── client.py                   # HTTP client (SSE / Streamable HTTP transport)

intentkit/tools/mcp/            # MCP → IntentKit tool adapters (tools layer)
├── wrapper.py                  # McpCategoryModule — provides get_tools/available
└── tool.py                     # McpToolTool — wraps individual MCP tools as IntentKit tools

intentkit/tools/mcp_{name}/    # Generated per-server tool category
├── __init__.py                 # Thin wrapper (auto-generated by scaffold script)
└── {name}.{ext}                # Icon (manually added)

scripts/scaffold_mcp_tools.py   # Generates the __init__.py boilerplate
```

> **Coarse, drift-proof config.** Remote MCP servers own their tool list and
> can change it at any time, so an MCP category does **not** snapshot or toggle
> individual tools. Its catalog carries a single server-level visibility
> control (keyed by the server name); when enabled, the agent gets whatever
> tools the server currently offers, discovered live at runtime. Because the
> catalog never enumerates tools, it can't go stale — no re-sync is needed when
> the server changes. The trade-off is no per-tool on/off in the UI. If you
> need per-tool control (or depend heavily on a provider's data), write a
> native tool category whose catalog is version-controlled alongside the code.

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
    name="mcp_myservice",               # Must match the dict key and tools/ folder name
    display_name="My Service",           # Human-readable name for UI
    description="What this service does",
    url="https://mcp.myservice.com/sse", # MCP server endpoint
    transport="sse",                     # "sse" or "streamable_http"
    api_key_config_attr="my_service_api_key",  # Attribute name in config.py (or None)
    api_key_header="Authorization",      # HTTP header for the key (or None)
    api_key_prefix="Bearer",             # Key prefix (or None for raw key)
    tags=["Developer Tools"],            # From the tags list above
    icon="/tools/mcp_myservice/myservice.svg",  # After adding the icon file
),
```

Key fields:
- `name` — must be `mcp_{service}` and match the `MCP_SERVERS` dict key
- `transport` — `"sse"` for Server-Sent Events, `"streamable_http"` for HTTP streaming
- `api_key_config_attr` — set to `None` if the server needs no auth
- `api_key_prefix` — set to `None` to send the raw key without prefix

#### 3. Run the scaffold script

```bash
source .venv/bin/activate
python scripts/scaffold_mcp_tools.py
```

This generates `intentkit/tools/mcp_myservice/__init__.py` — a thin wrapper
delegating to `McpCategoryModule`, which builds the catalog metadata (title,
description, tags, icon, single server-level entry) from the `McpServerDef`
at runtime.

#### 4. Add an icon

Download the service's official logo (square, SVG/PNG/JPEG/WebP) into the tool folder:
```
intentkit/tools/mcp_myservice/myservice.svg
```

Then set the `icon` field on the `McpServerDef` (see step 2).

#### 5. Verify

- The tool category is auto-discovered by the executor via `importlib.import_module(f"intentkit.tools.{k}")` — no manual registration needed.
- The `available()` check returns `True` if no API key is required, or if the system-level key is configured.

### How It Works at Runtime

1. **Gating**: `McpCategoryModule.get_tools()` exposes the server when the server name is present in the agent's tools list; otherwise it returns nothing.
2. **Discovery**: when on, the server is queried for its current tools (cached for 1 hour) and **all** of them are exposed — there is no per-tool filtering.
3. **Execution**: `McpToolTool._arun()` calls `call_mcp_tool()` which opens an MCP session, invokes the tool by its original (un-prefixed) name, and returns the text result.
4. **API key resolution**: The platform-level key from env/config is used.
