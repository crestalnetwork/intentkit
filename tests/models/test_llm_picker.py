from unittest.mock import patch

import pytest

from intentkit.models.llm_picker import pick_default_model, pick_summarize_model

# ── pick_summarize_model ─────────────────────────────────────────────


def test_pick_summarize_model_prefers_google_then_openai():
    with patch("intentkit.models.llm_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = "sk-test"
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = None
        mock_config.deepseek_api_key = None

        assert pick_summarize_model() == "gpt-5-mini"


def test_pick_summarize_model_xai_when_available():
    with patch("intentkit.models.llm_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = "xai-key"
        mock_config.deepseek_api_key = "ds-key"

        assert pick_summarize_model() == "grok-4-1-fast-non-reasoning"


def test_pick_summarize_model_raises_when_none():
    with patch("intentkit.models.llm_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = None
        mock_config.deepseek_api_key = None

        with pytest.raises(RuntimeError):
            _ = pick_summarize_model()


# ── pick_default_model ───────────────────────────────────────────────


def test_pick_default_model_prefers_google():
    with patch("intentkit.models.llm_picker.config") as mock_config:
        mock_config.google_api_key = "google-key"
        mock_config.openai_api_key = "sk-test"
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = None
        mock_config.deepseek_api_key = None

        assert pick_default_model() == "google/gemini-3-flash-preview"


def test_pick_default_model_openrouter_uses_minimax():
    with patch("intentkit.models.llm_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = None
        mock_config.openrouter_api_key = "or-key"
        mock_config.xai_api_key = None
        mock_config.deepseek_api_key = None

        assert pick_default_model() == "minimax/minimax-m2.5"


def test_pick_default_model_falls_to_deepseek():
    with patch("intentkit.models.llm_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = None
        mock_config.deepseek_api_key = "ds-key"

        assert pick_default_model() == "deepseek-chat"


def test_pick_default_model_raises_when_none():
    with patch("intentkit.models.llm_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = None
        mock_config.deepseek_api_key = None

        with pytest.raises(RuntimeError):
            _ = pick_default_model()
