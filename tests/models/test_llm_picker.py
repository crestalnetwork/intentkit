"""Tests for LLM picker functions.

These tests verify the picker logic (priority, fallback, error handling)
without hardcoding specific model names, since the model list changes often.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from intentkit.models.llm_picker import (
    list_available_model_ids,
    pick_broadest_knowledge_model,
    pick_chinese_writing_model,
    pick_default_model,
    pick_fastest_model,
    pick_finance_model,
    pick_lead_model,
    pick_lite_model,
    pick_long_context_model,
    pick_multimodal_model,
    pick_search_model,
    pick_smartest_model,
    pick_summarize_model,
    pick_writing_model,
)

# Category pickers that always resolve to a model (fallback instead of raising).
CATEGORY_PICKERS = [
    pick_lead_model,
    pick_lite_model,
    pick_smartest_model,
    pick_fastest_model,
    pick_multimodal_model,
    pick_writing_model,
    pick_chinese_writing_model,
    pick_finance_model,
    pick_search_model,
    pick_broadest_knowledge_model,
]


@contextmanager
def mock_llm_config(**keys):
    """Mock the config object in both llm and llm_picker modules.

    All API keys default to None unless explicitly provided.
    """
    defaults = {
        "google_api_key": None,
        "openai_api_key": None,
        "openrouter_api_key": None,
        "xai_api_key": None,
        "deepseek_api_key": None,
        "minimax_plan_api_key": None,
        "mimo_plan_api_key": None,
        "openai_compatible_api_key": None,
        "openai_compatible_base_url": None,
        "openai_compatible_model": None,
        "openai_compatible_model_lite": None,
        "anthropic_compatible_api_key": None,
        "anthropic_compatible_base_url": None,
        "anthropic_compatible_model": None,
        "anthropic_compatible_model_lite": None,
    }
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


# ── pick_lead_model ──────────────────────────────────────────────────


def test_picker_entries_reference_live_catalog_ids():
    """Every model a picker can return must be a live id in the raw catalog.

    Guards against a retired id lingering in a preference list: legacy_ids
    routing would silently mask the mistake and keep minting new agents
    with a retired id.
    """
    from pathlib import Path

    import yaml as pyyaml

    import intentkit.models.llm as llm_module
    from intentkit.models.llm_picker import _DEFAULT_FALLBACK_MODEL

    rows = pyyaml.safe_load(
        (Path(llm_module.__file__).with_name("llm.yaml")).read_text(encoding="utf-8")
    )
    live_ids = {row["id"] for row in rows}

    assert _DEFAULT_FALLBACK_MODEL in live_ids

    provider_keys = [
        "google_api_key",
        "openai_api_key",
        "openrouter_api_key",
        "xai_api_key",
        "deepseek_api_key",
        "minimax_plan_api_key",
        "mimo_plan_api_key",
    ]
    all_pickers = [pick_summarize_model, pick_default_model, *CATEGORY_PICKERS]
    for key in provider_keys:
        with mock_llm_config(**{key: "test-key"}):
            for picker in all_pickers:
                result = picker()
                assert result in live_ids, (
                    f"{picker.__name__} with only {key} returned {result!r}, "
                    "which is not a live catalog id"
                )
            try:
                result = pick_long_context_model()
            except RuntimeError:
                result = None
            if result is not None:
                assert result in live_ids


def test_pick_lead_model_on_google():
    """The lead runs a flash model at least as strong as the per-agent
    default; since Gemini 3 Flash retired, both land on 3.6 Flash."""
    with mock_llm_config(google_api_key="gk"):
        assert pick_lead_model() == "gemini-3.6-flash"
        assert pick_default_model() == "gemini-3.6-flash"


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


# ── category pickers (model-selection section) ───────────────────────


@pytest.mark.parametrize("picker", CATEGORY_PICKERS)
def test_category_picker_returns_model_when_provider_available(picker):
    """Each category picker returns a non-empty string for a configured provider."""
    with mock_llm_config(google_api_key="gk"):
        result = picker()
        assert isinstance(result, str) and len(result) > 0


@pytest.mark.parametrize("picker", CATEGORY_PICKERS)
def test_category_picker_falls_back_when_none(picker):
    """Each category picker falls back (does not raise) when nothing configured."""
    with mock_llm_config():
        result = picker()
        assert isinstance(result, str) and len(result) > 0


def test_category_picker_different_providers_yield_different_models():
    """A reasoning picker selects a provider-specific model."""
    with mock_llm_config(google_api_key="gk"):
        google_result = pick_smartest_model()
    with mock_llm_config(deepseek_api_key="dk"):
        deepseek_result = pick_smartest_model()
    assert google_result != deepseek_result


# ── list_available_model_ids ─────────────────────────────────────────


def test_list_available_model_ids_returns_sorted_unique_strings():
    """Returns a sorted list of unique model-id strings (possibly empty)."""
    result = list_available_model_ids()
    assert isinstance(result, list)
    assert all(isinstance(mid, str) for mid in result)
    assert result == sorted(set(result))
