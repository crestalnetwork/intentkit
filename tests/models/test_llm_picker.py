"""Tests for LLM picker functions.

These tests verify the picker logic (priority, fallback, error handling)
without hardcoding specific model names, since the model list changes often.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from intentkit.models.llm_picker import (
    pick_default_model,
    pick_long_context_model,
    pick_summarize_model,
)


@contextmanager
def mock_llm_config(**keys):
    """Mock the config object in both llm and llm_picker modules.

    All API keys default to None unless explicitly provided.
    """
    defaults = dict(
        google_api_key=None,
        openai_api_key=None,
        openrouter_api_key=None,
        xai_api_key=None,
        deepseek_api_key=None,
        minimax_api_key=None,
        openai_compatible_api_key=None,
        openai_compatible_base_url=None,
        openai_compatible_model=None,
        openai_compatible_model_lite=None,
        anthropic_compatible_api_key=None,
        anthropic_compatible_base_url=None,
        anthropic_compatible_model=None,
        anthropic_compatible_model_lite=None,
    )
    defaults.update(keys)
    with (
        patch("intentkit.models.llm.config") as m1,
        patch("intentkit.models.llm_picker.config") as m2,
    ):
        for k, v in defaults.items():
            setattr(m1, k, v)
            setattr(m2, k, v)
        yield


# ── pick_summarize_model ─────────────────────────────────────────────


def test_pick_summarize_model_returns_model_when_provider_available():
    """Returns a non-empty string when at least one provider is configured."""
    with mock_llm_config(openai_api_key="sk-test"):
        result = pick_summarize_model()
        assert isinstance(result, str) and len(result) > 0


def test_pick_summarize_model_raises_when_none():
    """Raises RuntimeError when no providers are configured."""
    with mock_llm_config():
        with pytest.raises(RuntimeError):
            pick_summarize_model()


def test_pick_summarize_model_different_providers_yield_different_models():
    """Different sole providers produce different model selections."""
    with mock_llm_config(google_api_key="gk"):
        google_result = pick_summarize_model()
    with mock_llm_config(deepseek_api_key="dk"):
        deepseek_result = pick_summarize_model()
    assert google_result != deepseek_result


# ── pick_default_model ───────────────────────────────────────────────


def test_pick_default_model_returns_model_when_provider_available():
    """Returns a non-empty string when at least one provider is configured."""
    with mock_llm_config(google_api_key="gk"):
        result = pick_default_model()
        assert isinstance(result, str) and len(result) > 0


def test_pick_default_model_fallback_when_none():
    """Returns a fallback string (not crash) when no providers are configured."""
    with mock_llm_config():
        result = pick_default_model()
        assert isinstance(result, str) and len(result) > 0


def test_pick_default_model_different_providers_yield_different_models():
    """Different sole providers produce different model selections."""
    with mock_llm_config(google_api_key="gk"):
        google_result = pick_default_model()
    with mock_llm_config(deepseek_api_key="dk"):
        deepseek_result = pick_default_model()
    assert google_result != deepseek_result


# ── pick_long_context_model ──────────────────────────────────────────


def test_pick_long_context_model_returns_model_when_provider_available():
    """Returns a non-empty string when at least one provider is configured."""
    with mock_llm_config(google_api_key="gk"):
        result = pick_long_context_model()
        assert isinstance(result, str) and len(result) > 0


def test_pick_long_context_model_raises_when_none():
    """Raises RuntimeError when no providers are configured."""
    with mock_llm_config():
        with pytest.raises(RuntimeError):
            pick_long_context_model()
