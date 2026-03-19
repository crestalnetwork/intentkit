"""Tests for image generation skills."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from intentkit.skills.image import Config, SkillStates, available, get_skills
from intentkit.skills.image.base import ImageGenerationInput
from intentkit.skills.image.gemini import GeminiImageFlash, GeminiImagePro
from intentkit.skills.image.gpt import GPTImageFlagship, GPTImageMini
from intentkit.skills.image.grok import GrokImage, GrokImagePro
from intentkit.skills.image.openrouter import FluxPro, Riverflow


def test_skill_metadata():
    """Test skill names, prices, and categories."""
    cases = [
        (GPTImageFlagship, "image_gpt", Decimal("50")),
        (GPTImageMini, "image_gpt_mini", Decimal("20")),
        (GeminiImagePro, "image_gemini_pro", Decimal("130")),
        (GeminiImageFlash, "image_gemini_flash", Decimal("70")),
        (GrokImagePro, "image_grok_pro", Decimal("70")),
        (GrokImage, "image_grok", Decimal("20")),
        (FluxPro, "image_flux_pro", Decimal("30")),
        (Riverflow, "image_riverflow", Decimal("20")),
    ]
    for cls, expected_name, expected_price in cases:
        skill = cls()
        assert skill.name == expected_name
        assert skill.price == expected_price
        assert skill.category == "image"
        assert skill.response_format == "content_and_artifact"


def test_input_schema_valid():
    """Test ImageGenerationInput accepts valid inputs."""
    inp = ImageGenerationInput(prompt="a cat")
    assert inp.prompt == "a cat"
    assert inp.images is None

    inp2 = ImageGenerationInput(
        prompt="edit this", images=["https://example.com/img.png"]
    )
    assert inp2.images == ["https://example.com/img.png"]


def test_input_schema_requires_prompt():
    """Test ImageGenerationInput requires prompt."""
    with pytest.raises(Exception):
        ImageGenerationInput()  # pyright: ignore[reportCallIssue]


class _MockConfig:
    """Mock config for testing available()."""

    def __init__(self, **kwargs: str | None):
        self.openai_api_key = kwargs.get("openai_api_key")
        self.google_api_key = kwargs.get("google_api_key")
        self.xai_api_key = kwargs.get("xai_api_key")
        self.openrouter_api_key = kwargs.get("openrouter_api_key")


def test_available_with_openai_key():
    with patch("intentkit.skills.image.system_config", _MockConfig(openai_api_key="k")):
        assert available() is True


def test_available_with_google_key():
    with patch("intentkit.skills.image.system_config", _MockConfig(google_api_key="k")):
        assert available() is True


def test_available_with_xai_key():
    with patch("intentkit.skills.image.system_config", _MockConfig(xai_api_key="k")):
        assert available() is True


def test_available_with_openrouter_key():
    with patch(
        "intentkit.skills.image.system_config", _MockConfig(openrouter_api_key="k")
    ):
        assert available() is True


def test_available_with_no_keys():
    with patch("intentkit.skills.image.system_config", _MockConfig()):
        assert available() is False


@pytest.mark.asyncio
async def test_get_skills_filters_by_state():
    """Test get_skills returns only enabled skills."""
    config: Config = {
        "enabled": True,
        "states": SkillStates(
            image_gpt="public",
            image_gpt_mini="disabled",
            image_gemini_pro="private",
            image_gemini_flash="disabled",
            image_grok_pro="disabled",
            image_grok="disabled",
            image_flux_pro="public",
            image_riverflow="disabled",
        ),
    }

    # Public only
    skills = await get_skills(config, is_private=False)
    names = {s.name for s in skills}
    assert "image_gpt" in names
    assert "image_flux_pro" in names
    assert "image_gpt_mini" not in names
    assert "image_gemini_pro" not in names  # private, not included

    # With private
    skills = await get_skills(config, is_private=True)
    names = {s.name for s in skills}
    assert "image_gpt" in names
    assert "image_gemini_pro" in names
    assert "image_flux_pro" in names
    assert "image_gpt_mini" not in names  # disabled


def test_native_key_checks():
    """Test _has_native_key for each provider."""
    with patch(
        "intentkit.skills.image.gpt.config",
        _MockConfig(openai_api_key="test"),
    ):
        assert GPTImageFlagship()._has_native_key() is True

    with patch("intentkit.skills.image.gpt.config", _MockConfig()):
        assert GPTImageFlagship()._has_native_key() is False

    with patch(
        "intentkit.skills.image.gemini.config",
        _MockConfig(google_api_key="test"),
    ):
        assert GeminiImagePro()._has_native_key() is True

    with patch("intentkit.skills.image.gemini.config", _MockConfig()):
        assert GeminiImagePro()._has_native_key() is False

    with patch(
        "intentkit.skills.image.grok.config",
        _MockConfig(xai_api_key="test"),
    ):
        assert GrokImagePro()._has_native_key() is True

    with patch("intentkit.skills.image.grok.config", _MockConfig()):
        assert GrokImagePro()._has_native_key() is False

    # OpenRouter-only skills always return False
    assert FluxPro()._has_native_key() is False
    assert Riverflow()._has_native_key() is False
