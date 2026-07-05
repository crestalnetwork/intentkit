"""Tests for the class-derived tool catalog."""

from intentkit.core.agent.tool_registry import get_tool_catalog


def test_get_tool_catalog_returns_categories():
    """Catalog must be keyed by category with the x-catalog wire shape inside."""
    catalog = get_tool_catalog()
    assert isinstance(catalog, dict)
    ui = catalog["ui"]
    assert isinstance(ui["title"], str) and ui["title"]
    assert isinstance(ui["description"], str)
    assert isinstance(ui["x-tags"], list)
    assert "ui_show_card" in ui["tools"]
    assert "ui_ask_user" in ui["tools"]
    assert ui["tools"]["ui_show_card"]["title"]
    assert ui["tools"]["ui_show_card"]["description"]


def test_web3_categories_flagged():
    """Web3 toolsets carry x-web3 so pickers can gate them on team wallets."""
    catalog = get_tool_catalog()
    assert catalog["erc20"].get("x-web3") is True
    assert "x-web3" not in catalog["http"]


def test_get_tool_catalog_has_no_empty_categories():
    """Every category must have at least one tool."""
    for category, payload in get_tool_catalog().items():
        assert len(payload["tools"]) > 0, f"Category '{category}' has no tools"
