from unittest.mock import patch

from intentkit.models.llm import LLMProvider, _load_default_llm_models


def test_llm_model_filtering():
    """Test that models are filtered based on available API keys in config."""

    # Case 1: No API keys configured
    with patch("intentkit.models.llm.config") as mock_config:
        # Explicitly set all keys to None
        mock_config.openai_api_key = None
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.eternal_api_key = None
        mock_config.reigent_api_key = None
        mock_config.venice_api_key = None

        models = _load_default_llm_models()

        # Verify restricted providers are filtered out
        restricted_providers = {
            LLMProvider.OPENAI,
            LLMProvider.GOOGLE,
            LLMProvider.DEEPSEEK,
            LLMProvider.XAI,
            LLMProvider.OPENROUTER,
            LLMProvider.ETERNAL,
            LLMProvider.REIGENT,
            LLMProvider.VENICE,
        }

        for model in models.values():
            assert model.provider not in restricted_providers, (
                f"Model {model.id} from provider {model.provider} should be filtered out when key is missing"
            )

    # Case 2: Enable OpenAI only
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = "sk-test-key"
        # Ensure others are None
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.eternal_api_key = None
        mock_config.reigent_api_key = None
        mock_config.venice_api_key = None

        models = _load_default_llm_models()

        # Verify OpenAI models are present
        openai_models = [m for m in models.values() if m.provider == LLMProvider.OPENAI]
        assert len(openai_models) > 0, "OpenAI models should be present when key is set"

        # Verify Google models are still missing
        google_models = [m for m in models.values() if m.provider == LLMProvider.GOOGLE]
        assert len(google_models) == 0, "Google models should be filtered out"

    # Case 3: Enable Multiple Providers
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = "sk-test-key"
        mock_config.google_api_key = "ai-test-key"
        # Others None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.eternal_api_key = None
        mock_config.reigent_api_key = None
        mock_config.venice_api_key = None

        models = _load_default_llm_models()

        openai_models = [m for m in models.values() if m.provider == LLMProvider.OPENAI]
        google_models = [m for m in models.values() if m.provider == LLMProvider.GOOGLE]

        assert len(openai_models) > 0
        assert len(google_models) > 0
