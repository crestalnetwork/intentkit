"""Validate/sanitize the agent ``tools`` config (flat list of tool names).

``validate_tools`` rejects anything that is not a list of known tool names,
raising ``IntentKitAPIError`` with key ``InvalidToolFormat`` (wrong shape) or
``InvalidToolName`` (unknown name). ``sanitize_tools`` is the lenient
counterpart: it dedupes, silently drops unknown names, and collapses an empty
result to ``None``.
"""

from typing import cast

import pytest

from intentkit.core.agent.tool_registry import sanitize_tools, validate_tools
from intentkit.utils.error import IntentKitAPIError


def test_validate_tools_accepts_valid_names():
    validate_tools(["ui_show_card", "ui_ask_user"])  # Should not raise


def test_validate_tools_accepts_names_across_categories():
    validate_tools(["ui_show_card", "erc20_get_balance"])  # Should not raise


def test_validate_tools_rejects_unknown_tool_name():
    with pytest.raises(IntentKitAPIError, match="fake_tool") as exc_info:
        validate_tools(["ui_show_card", "fake_tool"])
    assert exc_info.value.key == "InvalidToolName"


def test_validate_tools_rejects_non_list():
    # The legacy config shape was a dict; it must now be rejected outright.
    with pytest.raises(IntentKitAPIError, match="must be a list") as exc_info:
        validate_tools({"ui": {"enabled": True}})
    assert exc_info.value.key == "InvalidToolFormat"


def test_validate_tools_rejects_non_string_entries():
    with pytest.raises(IntentKitAPIError, match="must be strings") as exc_info:
        validate_tools(["ui_show_card", 42])
    assert exc_info.value.key == "InvalidToolFormat"


def test_validate_tools_allows_none():
    validate_tools(None)


def test_validate_tools_allows_empty_list():
    validate_tools([])


def test_sanitize_tools_keeps_valid_names_in_order():
    assert sanitize_tools(["ui_ask_user", "ui_show_card"]) == [
        "ui_ask_user",
        "ui_show_card",
    ]


def test_sanitize_tools_removes_unknown_names():
    result = sanitize_tools(["ui_show_card", "deleted_tool"])
    assert result == ["ui_show_card"]


def test_sanitize_tools_removes_duplicates():
    result = sanitize_tools(["ui_show_card", "ui_show_card", "ui_ask_user"])
    assert result == ["ui_show_card", "ui_ask_user"]


def test_sanitize_tools_drops_non_string_entries():
    dirty = cast(list[str], ["ui_show_card", 42])
    assert sanitize_tools(dirty) == ["ui_show_card"]


def test_sanitize_tools_returns_none_when_nothing_survives():
    assert sanitize_tools(["deleted_tool_1", "deleted_tool_2"]) is None


def test_sanitize_tools_returns_none_for_none():
    assert sanitize_tools(None) is None


def test_sanitize_tools_returns_none_for_empty_list():
    assert sanitize_tools([]) is None
