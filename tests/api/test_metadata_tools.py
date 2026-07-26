"""The toolset catalog endpoint feeds the frontends' tool picker.

Frontends hardcode their own form fields, so this endpoint (plus
``/metadata/llms``) is the only runtime data they need to render one.
"""

import json

import pytest

from app.common.metadata import get_tools


@pytest.mark.asyncio
async def test_categories_carry_their_display_metadata():
    response = await get_tools()
    catalog = json.loads(bytes(response.body))

    assert "erc20" in catalog
    erc20 = catalog["erc20"]
    assert erc20["title"] == "ERC20"
    assert erc20["description"]
    assert isinstance(erc20["x-tags"], list)


@pytest.mark.asyncio
async def test_tools_are_listed_with_titles():
    response = await get_tools()
    catalog = json.loads(bytes(response.body))

    erc20 = catalog["erc20"]
    assert "erc20_get_balance" in erc20["tools"]
    assert "erc20_transfer" in erc20["tools"]
    assert erc20["tools"]["erc20_transfer"]["title"]


@pytest.mark.asyncio
async def test_web3_flag_is_present_only_where_it_applies():
    """Pickers group on this flag, so it must reach the frontend."""
    response = await get_tools()
    catalog = json.loads(bytes(response.body))

    assert catalog["erc20"]["x-web3"] is True
    # Web3-themed data toolsets carry the flag too (no wallet semantics).
    assert catalog["dexscreener"]["x-web3"] is True
    # Non-web3 categories must not carry the flag at all.
    assert "x-web3" not in catalog["http"]


@pytest.mark.asyncio
async def test_icons_are_ready_to_use_as_urls():
    """`x-icon` is served as-is by GET /tools/{category}/{name}.{ext}."""
    response = await get_tools()
    catalog = json.loads(bytes(response.body))

    icons = [c["x-icon"] for c in catalog.values() if "x-icon" in c]
    assert icons, "expected at least one category to declare an icon"
    for icon in icons:
        assert icon.startswith("/tools/")


@pytest.mark.asyncio
async def test_response_is_cacheable():
    """The catalog is fixed for the deployment's lifetime."""
    response = await get_tools()
    assert "max-age" in response.headers["cache-control"]


@pytest.mark.asyncio
async def test_retired_toolsets_are_absent():
    """Only what this deployment can actually run is offered."""
    response = await get_tools()
    catalog = json.loads(bytes(response.body))

    for category, entry in catalog.items():
        assert entry["tools"], f"{category} was included with no usable tools"
