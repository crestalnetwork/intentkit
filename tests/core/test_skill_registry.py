"""Tests for get_valid_skills_registry utility."""

from intentkit.core.manager.service import get_valid_skills_registry


def test_get_valid_skills_registry_returns_categories():
    """Registry must return a dict keyed by category with skill dicts inside."""
    registry = get_valid_skills_registry()
    assert isinstance(registry, dict)
    assert "ui" in registry
    assert "ui_show_card" in registry["ui"]
    assert "ui_ask_user" in registry["ui"]
    assert isinstance(registry["ui"]["ui_show_card"], str)
    assert len(registry["ui"]["ui_show_card"]) > 0


def test_get_valid_skills_registry_has_no_empty_categories():
    """Every category must have at least one skill."""
    registry = get_valid_skills_registry()
    for category, skills in registry.items():
        assert len(skills) > 0, f"Category '{category}' has no skills"
