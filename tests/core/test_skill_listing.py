from intentkit.core.manager.service import get_skills_hierarchical_text


def test_hierarchical_text_includes_individual_skills():
    """Listing must include individual skill names under each category."""
    text = get_skills_hierarchical_text()
    assert "`ui_show_card`" in text
    assert "`ui_ask_user`" in text


def test_hierarchical_text_includes_skill_descriptions():
    """Each individual skill must have its description shown."""
    text = get_skills_hierarchical_text()
    # Check ui_show_card line has description content
    lines = text.split("\n")
    found = False
    for line in lines:
        if "`ui_show_card`" in line and ":" in line:
            # Should have description after the colon
            desc_part = line.split("`ui_show_card`:")[-1].strip()
            assert len(desc_part) > 10, "Description too short"
            found = True
            break
    assert found, "ui_show_card line with description not found"


def test_hierarchical_text_shows_category_then_skills():
    """Category line comes before its individual skills."""
    text = get_skills_hierarchical_text()
    lines = text.split("\n")
    ui_category_idx = None
    ui_skill_idx = None
    for i, line in enumerate(lines):
        if "**ui**" in line:
            ui_category_idx = i
        if "`ui_show_card`" in line and ui_category_idx is not None:
            ui_skill_idx = i
            break
    assert ui_category_idx is not None, "ui category not found"
    assert ui_skill_idx is not None, "ui_show_card not found after ui category"
    assert ui_skill_idx > ui_category_idx
