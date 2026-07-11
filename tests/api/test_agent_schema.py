"""The agent schema endpoint must attach the toolset catalog (x-catalog)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.common.schema import get_agent_schema


@pytest.mark.asyncio
async def test_agent_schema_includes_tool_catalog():
    """``tools`` is a flat list of tool names; the per-category catalog
    (titles, descriptions, tool maps) is attached as the ``x-catalog``
    extension so UIs can render a picker."""
    base_schema = {"properties": {"tools": {"type": "array"}}}
    with patch(
        "app.common.schema.Agent.get_json_schema",
        new=AsyncMock(return_value=base_schema),
    ):
        response = await get_agent_schema()

    schema = json.loads(bytes(response.body))
    catalog = schema["properties"]["tools"]["x-catalog"]

    assert "erc20" in catalog
    erc20 = catalog["erc20"]
    assert erc20["title"] == "ERC20"
    # Web3 flag must reach the frontend so pickers can group on it.
    assert erc20["x-web3"] is True
    assert "erc20_get_balance" in erc20["tools"]
    assert "erc20_transfer" in erc20["tools"]
    assert erc20["tools"]["erc20_transfer"]["title"]
    # Web3-themed data toolsets carry the flag too (no wallet semantics).
    assert catalog["dexscreener"]["x-web3"] is True
    # Non-web3 categories must not carry the flag at all.
    assert "x-web3" not in catalog["http"]


@pytest.mark.asyncio
async def test_agent_schema_strips_telegram_fields():
    """The endpoint must strip telegram fields even when the base schema has them."""
    base_schema = {
        "properties": {
            "tools": {"type": "array"},
            "telegram_entrypoint_enabled": {"type": "boolean"},
            "telegram_entrypoint_prompt": {"type": "string"},
            "telegram_config": {"type": "object"},
        }
    }
    with patch(
        "app.common.schema.Agent.get_json_schema",
        new=AsyncMock(return_value=base_schema),
    ):
        response = await get_agent_schema()

    properties = json.loads(bytes(response.body))["properties"]
    assert "tools" in properties
    for field in (
        "telegram_entrypoint_enabled",
        "telegram_entrypoint_prompt",
        "telegram_config",
    ):
        assert field not in properties


@pytest.mark.asyncio
async def test_agent_schema_excludes_retired_fields():
    """Retired agent fields were removed from ``schema.json``; the real
    endpoint output must not offer them to the form UI. Model tuning params
    are no longer user-configurable and the network follows the wallet."""
    response = await get_agent_schema()

    properties = json.loads(bytes(response.body))["properties"]
    assert "tools" in properties
    for field in (
        "temperature",
        "frequency_penalty",
        "presence_penalty",
        "network_id",
    ):
        assert field not in properties
