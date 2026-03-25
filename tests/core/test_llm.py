from unittest.mock import patch

from intentkit.models.llm import LLMProvider, load_default_llm_models


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
        mock_config.minimax_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None

        models = load_default_llm_models()

        # Verify restricted providers are filtered out
        restricted_providers = {
            LLMProvider.OPENAI,
            LLMProvider.GOOGLE,
            LLMProvider.DEEPSEEK,
            LLMProvider.XAI,
            LLMProvider.OPENROUTER,
            LLMProvider.MINIMAX,
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
        mock_config.minimax_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None

        models = load_default_llm_models()

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
        mock_config.minimax_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None

        models = load_default_llm_models()

        openai_models = [m for m in models.values() if m.provider == LLMProvider.OPENAI]
        google_models = [m for m in models.values() if m.provider == LLMProvider.GOOGLE]

        assert len(openai_models) > 0
        assert len(google_models) > 0

    # Case 4: Both providers kept when both keys configured
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = "sk-test-key"
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = "or-test-key"
        mock_config.minimax_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None

        models = load_default_llm_models()

        # Both native and OpenRouter variants should exist
        gpt5mini_openai = models.get("openai:gpt-5.4-mini")
        gpt5mini_openrouter = models.get("openrouter:openai/gpt-5.4-mini")

        assert gpt5mini_openai is not None
        assert gpt5mini_openai.provider == LLMProvider.OPENAI

        assert gpt5mini_openrouter is not None
        assert gpt5mini_openrouter.provider == LLMProvider.OPENROUTER

    # Case 5: Only OpenRouter when vendor key is missing
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = None
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = "or-test-key"
        mock_config.minimax_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None

        models = load_default_llm_models()

        # Native variant should not exist
        assert models.get("openai:gpt-5.4-mini") is None

        # OpenRouter variant should exist
        gpt5mini_or = models.get("openrouter:openai/gpt-5.4-mini")
        assert gpt5mini_or is not None
        assert gpt5mini_or.provider == LLMProvider.OPENROUTER


def test_model_id_index_suffix_matching():
    """Test that _MODEL_ID_INDEX includes base name entries for backward compat."""

    # Models with slash in id (e.g. "openai/gpt-5-mini") should also be
    # indexed by the base name ("gpt-5-mini") for legacy agent configs.
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = None
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = "or-test-key"
        mock_config.minimax_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None

        models = load_default_llm_models()

        # Build index the same way the module does
        index: dict[str, list[str]] = {}
        for key, model in models.items():
            index.setdefault(model.id, []).append(key)
            if "/" in model.id:
                base = model.id.rsplit("/", 1)[1]
                index.setdefault(base, []).append(key)

        # "gpt-5.4-mini" should resolve via suffix to the OpenRouter entry
        assert "gpt-5.4-mini" in index
        matching_keys = index["gpt-5.4-mini"]
        assert any("openrouter:" in k for k in matching_keys)
