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
    validate_tools(["http_get", "http_post"])  # Should not raise


def test_validate_tools_accepts_names_across_categories():
    validate_tools(["http_get", "erc20_get_balance"])  # Should not raise


def test_validate_tools_rejects_unknown_tool_name():
    with pytest.raises(IntentKitAPIError, match="fake_tool") as exc_info:
        validate_tools(["http_get", "fake_tool"])
    assert exc_info.value.key == "InvalidToolName"


def test_validate_tools_rejects_non_list():
    # The legacy config shape was a dict; it must now be rejected outright.
    with pytest.raises(IntentKitAPIError, match="must be a list") as exc_info:
        validate_tools({"http": {"enabled": True}})
    assert exc_info.value.key == "InvalidToolFormat"


def test_validate_tools_rejects_non_string_entries():
    with pytest.raises(IntentKitAPIError, match="must be strings") as exc_info:
        validate_tools(["http_get", 42])
    assert exc_info.value.key == "InvalidToolFormat"


def test_validate_tools_accepts_migrated_system_tool_names():
    # ui tools moved to auto-bound system tools; legacy configs still carrying
    # their names must not be rejected (e.g. re-importing an old export).
    validate_tools(["http_get", "ui_show_card", "ui_ask_user"])  # Should not raise


def test_sanitize_tools_drops_migrated_system_tool_names():
    # On update the migrated names are cleaned out of the stored config; the
    # capability itself is bound automatically as a system tool.
    assert sanitize_tools(["http_get", "ui_show_card", "ui_ask_user"]) == ["http_get"]


def test_validate_tools_allows_none():
    validate_tools(None)


def test_validate_tools_allows_empty_list():
    validate_tools([])


def test_sanitize_tools_keeps_valid_names_in_order():
    assert sanitize_tools(["http_post", "http_get"]) == [
        "http_post",
        "http_get",
    ]


def test_sanitize_tools_removes_unknown_names():
    result = sanitize_tools(["http_get", "deleted_tool"])
    assert result == ["http_get"]


def test_sanitize_tools_removes_duplicates():
    result = sanitize_tools(["http_get", "http_get", "http_post"])
    assert result == ["http_get", "http_post"]


def test_sanitize_tools_drops_non_string_entries():
    dirty = cast(list[str], ["http_get", 42])
    assert sanitize_tools(dirty) == ["http_get"]


def test_sanitize_tools_returns_none_when_nothing_survives():
    assert sanitize_tools(["deleted_tool_1", "deleted_tool_2"]) is None


def test_sanitize_tools_returns_none_for_none():
    assert sanitize_tools(None) is None


def test_sanitize_tools_returns_none_for_empty_list():
    assert sanitize_tools([]) is None
