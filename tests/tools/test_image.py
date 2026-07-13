"""Tests for image generation tools."""

import base64
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intentkit.tools.image import available, get_tools
from intentkit.tools.image.base import ImageGenerationInput
from intentkit.tools.image.gemini import (
    GeminiImageFlash,
    GeminiImageFlashLite,
    GeminiImagePro,
)
from intentkit.tools.image.gpt import GPTImageFlagship, GPTImageMini
from intentkit.tools.image.grok import GrokImage
from intentkit.tools.image.openrouter import FluxPro, Riverflow


def test_tool_metadata():
    """Test tool names, prices, and categories."""
    cases = [
        (GPTImageFlagship, "image_gpt", Decimal("80")),
        (GPTImageMini, "image_gpt_mini", Decimal("20")),
        (GeminiImagePro, "image_gemini_pro", Decimal("130")),
        (GeminiImageFlash, "image_gemini_flash", Decimal("70")),
        (GeminiImageFlashLite, "image_gemini_flash_lite", Decimal("35")),
        (GrokImage, "image_grok", Decimal("20")),
        (FluxPro, "image_flux_pro", Decimal("30")),
        (Riverflow, "image_riverflow", Decimal("20")),
    ]
    for cls, expected_name, expected_price in cases:
        tool = cls()
        assert tool.name == expected_name
        assert tool.price == expected_price
        assert tool.category == "image"
        assert tool.response_format == "content_and_artifact"


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
        self.google_genai_use_vertexai = kwargs.get("google_genai_use_vertexai", False)
        self.google_cloud_project = kwargs.get("google_cloud_project")
        self.xai_api_key = kwargs.get("xai_api_key")
        self.openrouter_api_key = kwargs.get("openrouter_api_key")
        self.minimax_plan_api_key = kwargs.get("minimax_plan_api_key")


def test_available_with_openai_key():
    with patch("intentkit.tools.image.system_config", _MockConfig(openai_api_key="k")):
        assert available() is True


def test_available_with_google_key():
    with patch("intentkit.tools.image.system_config", _MockConfig(google_api_key="k")):
        assert available() is True


def test_available_with_xai_key():
    with patch("intentkit.tools.image.system_config", _MockConfig(xai_api_key="k")):
        assert available() is True


def test_available_with_openrouter_key():
    with patch(
        "intentkit.tools.image.system_config", _MockConfig(openrouter_api_key="k")
    ):
        assert available() is True


def test_available_with_no_keys():
    with patch("intentkit.tools.image.system_config", _MockConfig()):
        assert available() is False


@pytest.mark.asyncio
async def test_get_tools_selects_by_name():
    """get_tools returns exactly the requested tools; unknown names are skipped."""
    tools = await get_tools(["image_gpt", "image_gemini_pro", "image_bogus"])
    names = [t.name for t in tools]
    assert names == ["image_gpt", "image_gemini_pro"]

    assert await get_tools([]) == []


def test_native_key_checks():
    """Test has_native_key for each provider."""
    with patch(
        "intentkit.tools.image.gpt.config",
        _MockConfig(openai_api_key="test"),
    ):
        assert GPTImageFlagship().has_native_key() is True

    with patch("intentkit.tools.image.gpt.config", _MockConfig()):
        assert GPTImageFlagship().has_native_key() is False

    with patch(
        "intentkit.tools.image.gemini.config",
        _MockConfig(google_api_key="test"),
    ):
        assert GeminiImagePro().has_native_key() is True

    with patch("intentkit.tools.image.gemini.config", _MockConfig()):
        assert GeminiImagePro().has_native_key() is False

    with patch(
        "intentkit.tools.image.grok.config",
        _MockConfig(xai_api_key="test"),
    ):
        assert GrokImage().has_native_key() is True

    with patch("intentkit.tools.image.grok.config", _MockConfig()):
        assert GrokImage().has_native_key() is False

    # OpenRouter-only tools always return False
    assert FluxPro().has_native_key() is False
    assert Riverflow().has_native_key() is False


@pytest.mark.asyncio
async def test_openrouter_payload_uses_image_only_modalities():
    """Regression: image-only OpenRouter models (flux/riverflow/seedream) reject
    modalities=["image","text"] with "No endpoints found". The SDK call from
    _generate_via_openrouter must request modalities=["image"] only.
    """
    fake_b64 = base64.b64encode(b"png-data").decode()
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    images=[
                        SimpleNamespace(
                            image_url=SimpleNamespace(
                                url=f"data:image/png;base64,{fake_b64}"
                            )
                        )
                    ],
                )
            )
        ]
    )
    mock_send = AsyncMock(return_value=response)
    mock_client = MagicMock(chat=MagicMock(send_async=mock_send))

    with patch("intentkit.tools.image.base.config") as mock_config:
        mock_config.openrouter_api_key = "test-key"
        with patch(
            "intentkit.tools.image.base.openrouter.OpenRouter",
            return_value=mock_client,
        ):
            result = await FluxPro()._generate_via_openrouter("a cat", None)

            assert result == b"png-data"
            call_kwargs = mock_send.call_args.kwargs
            assert call_kwargs["modalities"] == ["image"]
            assert call_kwargs["model"] == "black-forest-labs/flux.2-pro"
