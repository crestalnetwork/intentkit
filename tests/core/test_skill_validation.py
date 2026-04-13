import pytest

from intentkit.core.manager.service import sanitize_skills, validate_skills
from intentkit.utils.error import IntentKitAPIError


def test_validate_skills_accepts_valid_config():
    skills = {
        "ui": {
            "enabled": True,
            "states": {"ui_show_card": "public", "ui_ask_user": "private"},
        }
    }
    validate_skills(skills)  # Should not raise


def test_validate_skills_rejects_unknown_category():
    skills = {
        "nonexistent_category": {
            "enabled": True,
            "states": {"some_skill": "public"},
        }
    }
    with pytest.raises(IntentKitAPIError, match="nonexistent_category"):
        validate_skills(skills)


def test_validate_skills_rejects_unknown_skill_name():
    skills = {"ui": {"enabled": True, "states": {"fake_skill": "public"}}}
    with pytest.raises(IntentKitAPIError, match="fake_skill"):
        validate_skills(skills)


def test_validate_skills_rejects_invalid_state_value():
    skills = {"ui": {"enabled": True, "states": {"ui_show_card": "enabled"}}}
    with pytest.raises(IntentKitAPIError, match="ui_show_card"):
        validate_skills(skills)


def test_validate_skills_rejects_non_dict_category_config():
    skills = {"ui": "bad"}
    with pytest.raises(IntentKitAPIError, match="must be a dict"):
        validate_skills(skills)


def test_validate_skills_rejects_non_dict_states():
    skills = {"ui": {"enabled": True, "states": "bad"}}
    with pytest.raises(IntentKitAPIError, match="must be a dict"):
        validate_skills(skills)


def test_validate_skills_allows_none():
    validate_skills(None)


def test_validate_skills_allows_empty():
    validate_skills({})


def test_sanitize_skills_removes_unknown_category():
    skills = {
        "ui": {"enabled": True, "states": {"ui_show_card": "public"}},
        "nonexistent": {"enabled": True, "states": {"x": "public"}},
    }
    result = sanitize_skills(skills)
    assert result is not None
    assert "ui" in result
    assert "nonexistent" not in result


def test_sanitize_skills_removes_unknown_skill():
    skills = {
        "ui": {
            "enabled": True,
            "states": {"ui_show_card": "public", "deleted_skill": "public"},
        }
    }
    result = sanitize_skills(skills)
    assert result is not None
    assert "ui_show_card" in result["ui"]["states"]
    assert "deleted_skill" not in result["ui"]["states"]


def test_sanitize_skills_removes_category_if_all_skills_gone():
    skills = {
        "ui": {
            "enabled": True,
            "states": {"deleted_skill_1": "public", "deleted_skill_2": "public"},
        }
    }
    result = sanitize_skills(skills)
    assert "ui" not in (result or {})


def test_sanitize_skills_preserves_non_dict_config():
    """Sanitize should not silently wipe malformed configs."""
    skills = {
        "ui": "bad",
        "nonexistent": {"enabled": True, "states": {"x": "public"}},
    }
    result = sanitize_skills(skills)
    # ui is a valid category, so it's preserved even though config is malformed
    assert result is not None
    assert "ui" in result
    assert result["ui"] == "bad"
    # nonexistent category still dropped
    assert "nonexistent" not in result


def test_sanitize_skills_returns_none_for_none():
    assert sanitize_skills(None) is None


def test_sanitize_skills_returns_none_for_empty():
    assert sanitize_skills({}) is None
