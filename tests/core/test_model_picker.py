from unittest.mock import patch

import pytest

from intentkit.core.model_picker import pick_summarize_model


def test_pick_summarize_model_prefers_google_then_openai():
    with patch("intentkit.core.model_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = "sk-test"
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = None
        mock_config.deepseek_api_key = None

        assert pick_summarize_model() == "gpt-5-mini"


def test_pick_summarize_model_xai_when_available():
    with patch("intentkit.core.model_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = "xai-key"
        mock_config.deepseek_api_key = "ds-key"

        assert pick_summarize_model() == "grok-4-1-fast-non-reasoning"


def test_pick_summarize_model_raises_when_none():
    with patch("intentkit.core.model_picker.config") as mock_config:
        mock_config.google_api_key = None
        mock_config.openai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.xai_api_key = None
        mock_config.deepseek_api_key = None

        with pytest.raises(RuntimeError):
            _ = pick_summarize_model()
