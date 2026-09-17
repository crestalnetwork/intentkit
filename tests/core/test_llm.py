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


def _catalog_rows() -> list[dict]:
    """Raw llm.yaml rows, independent of which providers are configured."""
    from pathlib import Path

    import yaml as pyyaml

    import intentkit.models.llm as llm_module

    return pyyaml.safe_load(
        (Path(llm_module.__file__).with_name("llm.yaml")).read_text(encoding="utf-8")
    )


def test_minimax_catalog_contains_current_models():
    """The native MiniMax catalog mirrors the current subscription API lineup."""
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.minimax_plan_api_key = "test-key"
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None
        mock_config.anthropic_compatible_api_key = None
        mock_config.anthropic_compatible_base_url = None
        mock_config.anthropic_compatible_model = None
        models = load_default_llm_models()

    assert models["minimax:MiniMax-M3"].context_length == 1_000_000
    assert models["minimax:MiniMax-M2.7"].context_length == 204_800


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
        luna_openai = models.get("openai:gpt-luna")
        luna_openrouter = models.get("openrouter:openai/gpt-luna")

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
        assert models.get("openai:gpt-luna") is None

        # OpenRouter variant should exist
        luna_or = models.get("openrouter:openai/gpt-luna")
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

        mimo_pro = models.get("mimo_plan:mimo-pro")
        assert mimo_pro is not None
        assert mimo_pro.provider == LLMProvider.MIMO_PLAN
        assert mimo_pro.id == "mimo-pro"

        mimo_v25 = models.get("mimo_plan:mimo")
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

        # Models with slash in id (e.g. "openai/gpt-luna") should also be
        # indexed by the base name ("gpt-luna") for legacy agent configs.
        assert "gpt-luna" in index
        assert any("openrouter:" in k for k in index["gpt-luna"])

        # Every legacy id in the catalog routes to its successor and does not
        # linger as a live model.
        live_ids = {model.id for model in models.values()}
        for key, model in models.items():
            for legacy in model.legacy_ids:
                assert legacy not in live_ids
                assert key in index[legacy]

        # Explicit regression pins for retirements.
        assert index.get("x-ai/grok-4.3") == ["openrouter:x-ai/grok"]
        for retired in (
            "deepseek/deepseek-v4-flash-0731",
            "deepseek/deepseek-v4-flash-vision-exp",
        ):
            assert index.get(retired) == ["openrouter:deepseek/deepseek-flash"]
        assert index.get("qwen/qwen3.7-flash") == ["openrouter:qwen/qwen-flash"]
        assert index.get("z-ai/glm-4.7-flash") == ["openrouter:z-ai/glm-flash"]


def test_catalog_legacy_ids_are_disjoint():
    """Raw catalog invariants, independent of configured providers.

    Legacy ids must never collide with live ids or live base names, and no
    legacy id may be claimed by two entries — otherwise old agents would
    route to an arbitrary winner.
    """
    rows = _catalog_rows()
    claimed = {row["id"] for row in rows} | {
        row["api_id"] for row in rows if row.get("api_id")
    }
    live = claimed
    live_bases = {name.rsplit("/", 1)[1] for name in claimed if "/" in name}
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
    rows = _catalog_rows()
    for row in rows:
        levels = row.get("reasoning_levels")
        effort = row.get("reasoning_effort")
        if levels and effort is not None:
            assert effort in levels, (
                f"{row['id']}: reasoning_effort {effort!r} not in {levels}"
            )


# ── series ids / api_id ─────────────────────────────────────────────


def test_api_id_defaults_to_id():
    plain = _model_info("gemini-flash", LLMProvider.GOOGLE)
    assert plain.api_id == "gemini-flash"

    aliased = _model_info(
        "google/gemini-flash",
        LLMProvider.OPENROUTER,
        api_id="~google/gemini-flash-latest",
    )
    assert aliased.api_id == "~google/gemini-flash-latest"


def test_catalog_ids_are_versionless_series_ids():
    """Live ids never carry a version: bumps change ``api_id``/``name`` only.

    OpenRouter's "~family-latest" aliases are the only ``api_id`` form that
    tracks releases by itself, and they only exist on OpenRouter rows.
    """
    import re

    rows = _catalog_rows()
    for row in rows:
        assert not re.search(r"\d", row["id"]), f"{row['id']} carries a version"
        api_id = row.get("api_id", row["id"])
        assert api_id, row["id"]
        if api_id.startswith("~"):
            assert row["provider"] == "openrouter", row["id"]
            assert api_id.endswith("-latest"), row["id"]


def _install_catalog(monkeypatch, *models):
    import intentkit.models.llm as llm_module

    catalog = {f"{m.provider.value}:{m.id}": m for m in models}
    monkeypatch.setattr(llm_module, "AVAILABLE_MODELS", catalog)
    monkeypatch.setattr(llm_module, "_MODEL_ID_INDEX", build_model_id_index(catalog))


def test_resolve_model_id_normalizes_legacy_and_base_names(monkeypatch):
    from intentkit.models.llm import resolve_model_id

    _install_catalog(
        monkeypatch,
        _model_info(
            "gemini-flash", LLMProvider.GOOGLE, legacy_ids=["gemini-3.8-flash"]
        ),
        _model_info(
            "google/gemini-flash",
            LLMProvider.OPENROUTER,
            legacy_ids=["google/gemini-3.8-flash"],
        ),
        _model_info("openai/gpt-luna", LLMProvider.OPENROUTER),
    )

    # Live ids and composite keys are returned as the bare live id.
    assert resolve_model_id("gemini-flash") == "gemini-flash"
    assert resolve_model_id("openrouter:openai/gpt-luna") == "openai/gpt-luna"
    # Legacy ids route to their successor; the shared base name prefers the
    # native provider, like LLMModelInfo.get.
    assert resolve_model_id("gemini-3.8-flash") == "gemini-flash"
    assert resolve_model_id("google/gemini-3.8-flash") == "google/gemini-flash"
    assert resolve_model_id("gpt-luna") == "openai/gpt-luna"
    # Unknown ids pass through untouched so validation errors stay visible.
    assert resolve_model_id("not-a-model") == "not-a-model"


def test_api_id_is_indexed_like_a_live_id(monkeypatch):
    """The versioned id sent to (and reported by) the provider resolves too."""
    from intentkit.models.llm import resolve_model_id

    _install_catalog(
        monkeypatch,
        _model_info("grok", LLMProvider.XAI, api_id="grok-4.6"),
        _model_info(
            "google/gemini-flash-lite",
            LLMProvider.OPENROUTER,
            api_id="google/gemini-3.5-flash-lite",
        ),
    )
    assert resolve_model_id("grok-4.6") == "grok"
    assert (
        resolve_model_id("google/gemini-3.5-flash-lite") == "google/gemini-flash-lite"
    )
    assert resolve_model_id("gemini-3.5-flash-lite") == "google/gemini-flash-lite"


def test_agent_model_field_normalizes_legacy_ids(monkeypatch):
    """Agents saved with a retired id read back with the live series id."""
    from intentkit.models.agent import AgentUpdate

    _install_catalog(
        monkeypatch,
        _model_info(
            "gemini-flash", LLMProvider.GOOGLE, legacy_ids=["gemini-3.8-flash"]
        ),
    )

    assert AgentUpdate(name="t", model="gemini-3.8-flash").model == "gemini-flash"
    assert AgentUpdate(name="t", model="gemini-flash").model == "gemini-flash"
    assert AgentUpdate(name="t", model="custom-model").model == "custom-model"
