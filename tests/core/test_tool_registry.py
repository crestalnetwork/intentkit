"""Tests for the class-derived tool catalog."""

from intentkit.core.agent.tool_registry import get_tool_catalog


def test_get_tool_catalog_returns_categories():
    """Catalog must be keyed by category with the x-catalog wire shape inside."""
    catalog = get_tool_catalog()
    assert isinstance(catalog, dict)
    http = catalog["http"]
    assert isinstance(http["title"], str) and http["title"]
    assert isinstance(http["description"], str)
    assert isinstance(http["x-tags"], list)
    assert "http_get" in http["tools"]
    assert "http_post" in http["tools"]
    assert http["tools"]["http_get"]["title"]
    assert http["tools"]["http_get"]["description"]


def test_ui_tools_absent_from_catalog():
    """ui_show_card / ui_ask_user moved to system tools and must not be
    user-selectable anymore."""
    catalog = get_tool_catalog()
    assert "ui" not in catalog
    all_tool_names = {name for cat in catalog.values() for name in cat["tools"]}
    assert "ui_show_card" not in all_tool_names
    assert "ui_ask_user" not in all_tool_names


def test_web3_categories_flagged():
    """Web3 toolsets carry x-web3 so pickers can gate them on team wallets."""
    catalog = get_tool_catalog()
    assert catalog["erc20"].get("x-web3") is True
    assert "x-web3" not in catalog["http"]


def test_get_tool_catalog_has_no_empty_categories():
    """Every category must have at least one tool."""
    for category, payload in get_tool_catalog().items():
        assert len(payload["tools"]) > 0, f"Category '{category}' has no tools"
