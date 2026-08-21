from decimal import Decimal
from unittest.mock import patch

from intentkit.models.llm import (
    LLMModelInfo,
    LLMProvider,
    build_model_id_index,
    load_default_llm_models,
)


def _model_info(model_id: str, provider: LLMProvider, **overrides) -> LLMModelInfo:
    """Minimal valid LLMModelInfo for index tests."""
    attrs = {
        "id": model_id,
        "name": model_id,
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
        mock_config.minimax_plan_api_key = None
        mock_config.mimo_plan_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None
        mock_config.anthropic_compatible_api_key = None
        mock_config.anthropic_compatible_base_url = None
        mock_config.anthropic_compatible_model = None

        models = load_default_llm_models()

        # Verify restricted providers are filtered out
        restricted_providers = {
            LLMProvider.OPENAI,
            LLMProvider.GOOGLE,
            LLMProvider.DEEPSEEK,
            LLMProvider.XAI,
            LLMProvider.OPENROUTER,
            LLMProvider.MINIMAX,
            LLMProvider.MIMO_PLAN,
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
        mock_config.minimax_plan_api_key = None
        mock_config.mimo_plan_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None
        mock_config.anthropic_compatible_api_key = None
        mock_config.anthropic_compatible_base_url = None
        mock_config.anthropic_compatible_model = None

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
        mock_config.minimax_plan_api_key = None
        mock_config.mimo_plan_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None
        mock_config.anthropic_compatible_api_key = None
        mock_config.anthropic_compatible_base_url = None
        mock_config.anthropic_compatible_model = None

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
        mock_config.minimax_plan_api_key = None
        mock_config.mimo_plan_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None
        mock_config.anthropic_compatible_api_key = None
        mock_config.anthropic_compatible_base_url = None
        mock_config.anthropic_compatible_model = None

        models = load_default_llm_models()

        # Both native and OpenRouter variants should exist
        luna_openai = models.get("openai:gpt-5.6-luna")
        luna_openrouter = models.get("openrouter:openai/gpt-5.6-luna")

        assert luna_openai is not None
        assert luna_openai.provider == LLMProvider.OPENAI

        assert luna_openrouter is not None
        assert luna_openrouter.provider == LLMProvider.OPENROUTER

    # Case 5: Only OpenRouter when vendor key is missing
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

        # Native variant should not exist
        assert models.get("openai:gpt-5.6-luna") is None

        # OpenRouter variant should exist
        luna_or = models.get("openrouter:openai/gpt-5.6-luna")
        assert luna_or is not None
        assert luna_or.provider == LLMProvider.OPENROUTER

    # Case 6: MiMo Token Plan models load when only MIMO_PLAN key is set
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = None
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.minimax_plan_api_key = None
        mock_config.mimo_plan_api_key = "mimo-test-key"
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None
        mock_config.anthropic_compatible_api_key = None
        mock_config.anthropic_compatible_base_url = None
        mock_config.anthropic_compatible_model = None

        models = load_default_llm_models()

        mimo_pro = models.get("mimo_plan:mimo-v2.5-pro")
        assert mimo_pro is not None
        assert mimo_pro.provider == LLMProvider.MIMO_PLAN
        assert mimo_pro.id == "mimo-v2.5-pro"

        mimo_v25 = models.get("mimo_plan:mimo-v2.5")
        assert mimo_v25 is not None
        assert mimo_v25.provider == LLMProvider.MIMO_PLAN


def test_model_id_index_suffix_and_legacy_matching():
    """The id index covers base names after "/" and legacy_ids routing."""

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

        index = build_model_id_index(models)

        # Models with slash in id (e.g. "openai/gpt-5.6-luna") should also be
        # indexed by the base name ("gpt-5.6-luna") for legacy agent configs.
        assert "gpt-5.6-luna" in index
        assert any("openrouter:" in k for k in index["gpt-5.6-luna"])

        # Every legacy id in the catalog routes to its successor and does not
        # linger as a live model.
        live_ids = {model.id for model in models.values()}
        for key, model in models.items():
            for legacy in model.legacy_ids:
                assert legacy not in live_ids
                assert key in index[legacy]

        # Explicit regression pin for one retirement.
        assert index.get("x-ai/grok-4.3") == ["openrouter:x-ai/grok-4.6"]


def test_catalog_legacy_ids_are_disjoint():
    """Raw catalog invariants, independent of configured providers.

    Legacy ids must never collide with live ids or live base names, and no
    legacy id may be claimed by two entries — otherwise old agents would
    route to an arbitrary winner.
    """
    from pathlib import Path

    import yaml as pyyaml

    import intentkit.models.llm as llm_module

    rows = pyyaml.safe_load(
        (Path(llm_module.__file__).with_name("llm.yaml")).read_text(encoding="utf-8")
    )
    live = {row["id"] for row in rows}
    live_bases = {row["id"].rsplit("/", 1)[1] for row in rows if "/" in row["id"]}
    seen: set[str] = set()
    for row in rows:
        for legacy in row.get("legacy_ids", []):
            assert legacy not in live, f"{legacy} is both legacy and live"
            assert legacy not in live_bases, f"{legacy} collides with a live base name"
            assert legacy not in seen, f"{legacy} claimed by multiple entries"
            seen.add(legacy)


def test_model_id_index_legacy_collision_ignored():
    """A legacy id (or its base name) colliding with a live claim is ignored."""

    live = _model_info("vendor/live-model", LLMProvider.OPENROUTER)
    # Collides with the live full id, its base name, and — via the base name
    # of a slash-prefixed legacy id — the live base name again.
    usurper = _model_info(
        "usurper",
        LLMProvider.OPENAI,
        legacy_ids=[
            "vendor/live-model",
            "live-model",
            "other-vendor/live-model",
            "gone-model",
        ],
    )
    index = build_model_id_index(
        {
            "openrouter:vendor/live-model": live,
            "openai:usurper": usurper,
        }
    )
    # The live model keeps exclusive ownership of its id and base name.
    assert index["vendor/live-model"] == ["openrouter:vendor/live-model"]
    assert index["live-model"] == ["openrouter:vendor/live-model"]
    # A non-colliding slash-prefixed legacy id still routes by full id...
    assert index["other-vendor/live-model"] == ["openai:usurper"]
    # ...and the genuinely retired id routes to the successor.
    assert index["gone-model"] == ["openai:usurper"]


def test_catalog_reasoning_effort_within_levels():
    """Every catalog default effort must be one of that model's own levels.

    A model bump that drops a level (3.7 Flash lost "minimal") would otherwise
    leave a default the clamp has to silently rewrite on every request.
    """
    from pathlib import Path

    import yaml as pyyaml

    import intentkit.models.llm as llm_module

    rows = pyyaml.safe_load(
        (Path(llm_module.__file__).with_name("llm.yaml")).read_text(encoding="utf-8")
    )
    for row in rows:
        levels = row.get("reasoning_levels")
        effort = row.get("reasoning_effort")
        if levels and effort is not None:
            assert effort in levels, (
                f"{row['id']}: reasoning_effort {effort!r} not in {levels}"
            )
