"""Tests for the agent-level reasoning effort: clamping and provider mapping."""

# Provider kwargs land on chat-model subclasses create_instance returns as
# BaseChatModel; runtime attribute access is intentional here.
# pyright: reportAttributeAccessIssue=false

from decimal import Decimal
from unittest.mock import patch

import pytest

from intentkit.models.llm import (
    XAILLM,
    DeepseekLLM,
    GoogleLLM,
    LLMModelInfo,
    LLMProvider,
    MimoPlanLLM,
    MiniMaxLLM,
    OpenAILLM,
    OpenRouterLLM,
)


def _info(provider: LLMProvider, **overrides) -> LLMModelInfo:
    attrs = {
        "id": "test-model",
        "name": "test-model",
        "provider": provider,
        "input_price": Decimal("1"),
        "output_price": Decimal("2"),
        "context_length": 100000,
        "output_length": 8192,
        "intelligence": 3,
        "speed": 3,
        **overrides,
    }
    return LLMModelInfo.model_validate(attrs)


# ---------------------------------------------------------------------------
# resolve_reasoning_effort clamping
# ---------------------------------------------------------------------------


def test_resolve_defaults_to_catalog_effort():
    info = _info(
        LLMProvider.OPENROUTER,
        reasoning_effort="high",
        reasoning_levels=["none", "high"],
    )
    assert info.resolve_reasoning_effort(None) == "high"


def test_resolve_passes_through_without_levels():
    info = _info(LLMProvider.OPENAI_COMPATIBLE, reasoning_effort="high")
    assert info.resolve_reasoning_effort("minimal") == "minimal"
    assert info.resolve_reasoning_effort(None) == "high"


def test_resolve_none_clamps_to_weakest_when_undisableable():
    # Grok 4.5 / Gemini 3.1 Pro shape: reasoning cannot be turned off.
    info = _info(
        LLMProvider.XAI,
        reasoning_effort="high",
        reasoning_levels=["low", "medium", "high"],
    )
    assert info.resolve_reasoning_effort("none") == "low"
    assert info.resolve_reasoning_effort("minimal") == "low"
    assert info.resolve_reasoning_effort("max") == "high"


def test_resolve_never_clamps_positive_request_to_none():
    # DeepSeek shape: only off/high/max exist; a "low" request must stay on.
    info = _info(
        LLMProvider.DEEPSEEK,
        reasoning_effort="none",
        reasoning_levels=["none", "high", "max"],
    )
    assert info.resolve_reasoning_effort("low") == "high"
    assert info.resolve_reasoning_effort("xhigh") == "max"
    assert info.resolve_reasoning_effort("none") == "none"


def test_resolve_single_level_model():
    # Kimi K2.7 Code shape: thinking always on, no control.
    info = _info(
        LLMProvider.OPENROUTER,
        reasoning_effort="high",
        reasoning_levels=["high"],
    )
    for requested in ("none", "minimal", "low", "medium", "xhigh", "max", None):
        assert info.resolve_reasoning_effort(requested) == "high"


# ---------------------------------------------------------------------------
# provider mapping in create_instance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openrouter_forwards_clamped_effort():
    info = _info(
        LLMProvider.OPENROUTER,
        reasoning_effort="high",
        reasoning_levels=["none", "high"],
    )
    model = OpenRouterLLM(model_name=info.id, reasoning_effort="low", info=info)
    with (
        patch("intentkit.models.llm.config") as mock_config,
        patch.object(LLMModelInfo, "get", return_value=info),
    ):
        mock_config.openrouter_api_key = "test-key"
        instance = await model.create_instance()
    assert instance.reasoning == {"effort": "high"}


@pytest.mark.asyncio
async def test_openrouter_forwards_none_effort():
    # Hybrid upstreams rely on an explicit "none" to suppress default thinking.
    info = _info(
        LLMProvider.OPENROUTER,
        reasoning_effort="none",
        reasoning_levels=["none", "high"],
    )
    model = OpenRouterLLM(model_name=info.id, info=info)
    with (
        patch("intentkit.models.llm.config") as mock_config,
        patch.object(LLMModelInfo, "get", return_value=info),
    ):
        mock_config.openrouter_api_key = "test-key"
        instance = await model.create_instance()
    assert instance.reasoning == {"effort": "none"}


@pytest.mark.asyncio
async def test_openai_sends_explicit_none():
    info = _info(
        LLMProvider.OPENAI,
        reasoning_effort="high",
        reasoning_levels=["none", "low", "medium", "high", "xhigh", "max"],
    )
    model = OpenAILLM(model_name=info.id, reasoning_effort="none", info=info)
    with (
        patch("intentkit.models.llm.config") as mock_config,
        patch.object(LLMModelInfo, "get", return_value=info),
    ):
        mock_config.openai_api_key = "test-key"
        instance = await model.create_instance()
    assert instance.reasoning_effort == "none"


@pytest.mark.asyncio
async def test_deepseek_toggles_thinking_and_maps_effort():
    info = _info(
        LLMProvider.DEEPSEEK,
        reasoning_effort="none",
        reasoning_levels=["none", "high", "max"],
    )
    with (
        patch("intentkit.models.llm.config") as mock_config,
        patch.object(LLMModelInfo, "get", return_value=info),
    ):
        mock_config.deepseek_api_key = "test-key"
        off = await DeepseekLLM(model_name=info.id, info=info).create_instance()
        on = await DeepseekLLM(
            model_name=info.id, reasoning_effort="xhigh", info=info
        ).create_instance()
    assert off.extra_body == {"thinking": {"type": "disabled"}}
    assert on.extra_body == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "max",
    }


@pytest.mark.asyncio
async def test_xai_never_sends_none():
    info = _info(
        LLMProvider.XAI,
        reasoning_effort="high",
        reasoning_levels=["low", "medium", "high"],
    )
    model = XAILLM(model_name=info.id, reasoning_effort="none", info=info)
    with (
        patch("intentkit.models.llm.config") as mock_config,
        patch.object(LLMModelInfo, "get", return_value=info),
    ):
        mock_config.xai_api_key = "test-key"
        instance = await model.create_instance()
    assert instance.reasoning_effort == "low"


@pytest.mark.asyncio
async def test_google_maps_to_thinking_level():
    info = _info(
        LLMProvider.GOOGLE,
        reasoning_effort="high",
        reasoning_levels=["minimal", "low", "medium", "high"],
    )
    model = GoogleLLM(model_name=info.id, reasoning_effort="max", info=info)
    with (
        patch("intentkit.models.llm.config") as mock_config,
        patch.object(LLMModelInfo, "get", return_value=info),
    ):
        mock_config.google_api_key = "test-key"
        mock_config.google_genai_use_vertexai = False
        instance = await model.create_instance()
    assert instance.thinking_level == "high"


@pytest.mark.asyncio
async def test_minimax_always_sends_thinking_toggle():
    # MiniMax's Anthropic-compatible endpoint defaults to thinking disabled,
    # so the toggle must be sent explicitly even for the catalog default.
    info = _info(
        LLMProvider.MINIMAX,
        reasoning_effort="high",
        reasoning_levels=["none", "high"],
    )
    with (
        patch("intentkit.models.llm.config") as mock_config,
        patch.object(LLMModelInfo, "get", return_value=info),
    ):
        mock_config.minimax_plan_api_key = "test-key"
        on = await MiniMaxLLM(model_name=info.id, info=info).create_instance()
        off = await MiniMaxLLM(
            model_name=info.id, reasoning_effort="none", info=info
        ).create_instance()
    assert on.thinking == {"type": "adaptive"}
    assert off.thinking == {"type": "disabled"}


@pytest.mark.asyncio
async def test_mimo_toggles_thinking():
    info = _info(
        LLMProvider.MIMO_PLAN,
        reasoning_effort="high",
        reasoning_levels=["none", "high"],
    )
    with (
        patch("intentkit.models.llm.config") as mock_config,
        patch.object(LLMModelInfo, "get", return_value=info),
    ):
        mock_config.mimo_plan_api_key = "test-key"
        on = await MimoPlanLLM(model_name=info.id, info=info).create_instance()
        off = await MimoPlanLLM(
            model_name=info.id, reasoning_effort="none", info=info
        ).create_instance()
    assert on.extra_body == {"thinking": {"type": "enabled"}}
    assert off.extra_body == {"thinking": {"type": "disabled"}}
