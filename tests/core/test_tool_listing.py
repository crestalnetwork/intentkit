from intentkit.core.agent.tool_registry import get_tools_hierarchical_text


def test_hierarchical_text_includes_individual_tools():
    """Listing must include individual tool names under each category."""
    text = get_tools_hierarchical_text()
    assert "`http_get`" in text
    assert "`http_post`" in text


def test_hierarchical_text_includes_tool_descriptions():
    """Each individual tool must have its description shown."""
    text = get_tools_hierarchical_text()
    # Check http_get line has description content
    lines = text.split("\n")
    found = False
    for line in lines:
        if "`http_get`" in line and ":" in line:
            # Should have description after the colon
            desc_part = line.split("`http_get`:")[-1].strip()
            assert len(desc_part) > 10, "Description too short"
            found = True
            break
    assert found, "http_get line with description not found"


def test_hierarchical_text_shows_category_then_tools():
    """Category line comes before its individual tools."""
    text = get_tools_hierarchical_text()
    lines = text.split("\n")
    http_category_idx = None
    http_tool_idx = None
    for i, line in enumerate(lines):
        if "**http**" in line:
            http_category_idx = i
        if "`http_get`" in line and http_category_idx is not None:
            http_tool_idx = i
            break
    assert http_category_idx is not None, "http category not found"
    assert http_tool_idx is not None, "http_get not found after http category"
    assert http_tool_idx > http_category_idx


def test_system_tools_not_listed():
    """System tools are auto-bound, never user-selectable, so they must not
    appear in the catalog listing."""
    text = get_tools_hierarchical_text()
    assert "ui_show_card" not in text
    assert "ui_ask_user" not in text
    assert "current_time" not in text
