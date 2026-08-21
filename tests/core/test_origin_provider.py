"""Tests for the origin_provider field and OpenRouter upstream-provider locking."""

from unittest.mock import patch

import pytest
from langchain_openrouter import ChatOpenRouter

from intentkit.models.llm import (
    LLMModelInfo,
    OpenRouterLLM,
    load_default_llm_models,
)


def _openrouter_info(origin_provider: str | None = None) -> LLMModelInfo:
    return LLMModelInfo.model_validate(
        {
            "id": "anthropic/claude-opus-5",
            "name": "Claude Opus 5",
            "provider": "openrouter",
            "origin_provider": origin_provider,
            "input_price": "5",
            "output_price": "25",
            "context_length": 1000000,
            "output_length": 128000,
            "intelligence": 5,
            "speed": 2,
        }
    )


def test_origin_provider_defaults_to_none():
    """origin_provider is optional and defaults to None when omitted."""
    info = _openrouter_info()
    assert info.origin_provider is None


def test_origin_provider_loaded_from_catalog():
    """The YAML catalog populates origin_provider on locked OpenRouter models."""
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = None
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = "or-test-key"
        mock_config.minimax_plan_api_key = None
        mock_config.mimo_plan_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None
        mock_config.anthropic_compatible_api_key = None
        mock_config.anthropic_compatible_base_url = None
        mock_config.anthropic_compatible_model = None

        models = load_default_llm_models()

    # Locked models carry their pinned upstream provider.
    opus = models.get("openrouter:anthropic/claude-opus-5")
    assert opus is not None
    assert opus.origin_provider == "anthropic"

    kimi = models.get("openrouter:moonshotai/kimi-k3")
    assert kimi is not None
    assert kimi.origin_provider == "moonshotai"

    grok = models.get("openrouter:x-ai/grok-4.6")
    assert grok is not None
    assert grok.origin_provider == "xai"

    for gemini_id in ("google/gemini-3.7-flash", "google/gemini-3.5-flash-lite"):
        gemini = models.get(f"openrouter:{gemini_id}")
        assert gemini is not None
        assert gemini.origin_provider == "google-vertex/global"

    glm = models.get("openrouter:z-ai/glm-5.3")
    assert glm is not None
    assert glm.origin_provider == "z-ai"

    # Unlocked OpenRouter models (no first-party endpoint) leave routing
    # to OpenRouter.
    glm_flash = models.get("openrouter:z-ai/glm-4.7-flash")
    assert glm_flash is not None
    assert glm_flash.origin_provider is None


@pytest.mark.asyncio
async def test_openrouter_pins_provider_when_origin_set(monkeypatch):
    """create_instance hard-locks the upstream provider when origin_provider is set."""
    info = _openrouter_info(origin_provider="anthropic")

    async def fake_get(model_id: str) -> LLMModelInfo:
        return info

    monkeypatch.setattr(LLMModelInfo, "get", staticmethod(fake_get))

    llm = OpenRouterLLM(model_name=info.id, info=info)
    instance = await llm.create_instance()

    assert isinstance(instance, ChatOpenRouter)
    assert instance.openrouter_provider == {
        "order": ["anthropic"],
        "allow_fallbacks": False,
    }


@pytest.mark.asyncio
async def test_openrouter_leaves_routing_open_without_origin(monkeypatch):
    """create_instance sends no provider routing when origin_provider is unset."""
    info = _openrouter_info(origin_provider=None)

    async def fake_get(model_id: str) -> LLMModelInfo:
        return info

    monkeypatch.setattr(LLMModelInfo, "get", staticmethod(fake_get))

    llm = OpenRouterLLM(model_name=info.id, info=info)
    instance = await llm.create_instance()

    assert isinstance(instance, ChatOpenRouter)
    assert instance.openrouter_provider is None
