"""Tests for cached input token pricing support."""

from decimal import Decimal
from unittest.mock import patch

import pytest

import intentkit.models.llm as llm_module
from intentkit.core.engine import extract_cached_input_tokens
from intentkit.models.llm import LLMModelInfo, LLMProvider, load_default_llm_models

# ---------------------------------------------------------------------------
# extract_cached_input_tokens
# ---------------------------------------------------------------------------


class _Msg:
    """Minimal message stub with controllable usage_metadata."""

    def __init__(self, usage_metadata=None):
        self.usage_metadata = usage_metadata


def test_extract_cached_no_usage_metadata():
    msg = _Msg(usage_metadata=None)
    assert extract_cached_input_tokens(msg) == 0


def test_extract_cached_no_input_token_details():
    msg = _Msg(usage_metadata={"input_tokens": 100, "output_tokens": 50})
    assert extract_cached_input_tokens(msg) == 0


def test_extract_cached_empty_input_token_details():
    msg = _Msg(
        usage_metadata={
            "input_tokens": 100,
            "input_token_details": {},
        }
    )
    assert extract_cached_input_tokens(msg) == 0


def test_extract_cached_with_cache_read():
    msg = _Msg(
        usage_metadata={
            "input_tokens": 200,
            "input_token_details": {"cache_read": 150, "audio": 10},
        }
    )
    assert extract_cached_input_tokens(msg) == 150


def test_extract_cached_object_without_attribute():
    """Works on plain objects that have no usage_metadata attribute at all."""

    class NoMeta:
        pass

    assert extract_cached_input_tokens(NoMeta()) == 0


# ---------------------------------------------------------------------------
# LLMModelInfo.calculate_cost — cached input pricing
# ---------------------------------------------------------------------------


def _make_model_info(**overrides) -> LLMModelInfo:
    from datetime import UTC, datetime

    defaults = dict(
        id="test-model",
        name="Test Model",
        provider=LLMProvider.OPENAI,
        enabled=True,
        input_price=Decimal("3"),  # $3 per 1M tokens
        cached_input_price=Decimal("0.3"),  # $0.3 per 1M tokens
        output_price=Decimal("15"),  # $15 per 1M tokens
        context_length=100000,
        output_length=4096,
        intelligence=5,
        speed=3,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return LLMModelInfo(**defaults)


@pytest.mark.asyncio
async def test_calculate_cost_no_cached_tokens(monkeypatch):
    """All input tokens billed at input_price when no cache hits."""
    model = _make_model_info()
    monkeypatch.setattr(llm_module, "credit_per_usdc", Decimal("1000"))

    # 1000 input + 500 output, 0 cached
    # input:  1000 * 1000 * 3 / 1_000_000 = 3
    # output: 1000 * 500 * 15 / 1_000_000 = 7.5
    cost = await model.calculate_cost(1000, 500, cached_input_tokens=0)
    assert cost == Decimal("10.5000")


@pytest.mark.asyncio
async def test_calculate_cost_all_cached(monkeypatch):
    """When all input tokens are cached, cached_input_price applies to all."""
    model = _make_model_info()
    monkeypatch.setattr(llm_module, "credit_per_usdc", Decimal("1000"))

    # 1000 input (all cached), 500 output
    # cached: 1000 * 1000 * 0.3 / 1_000_000 = 0.3
    # output: 1000 * 500 * 15 / 1_000_000   = 7.5
    cost = await model.calculate_cost(1000, 500, cached_input_tokens=1000)
    assert cost == Decimal("7.8000")


@pytest.mark.asyncio
async def test_calculate_cost_partial_cached(monkeypatch):
    """Split billing: cached portion at cached_input_price, rest at input_price."""
    model = _make_model_info()
    monkeypatch.setattr(llm_module, "credit_per_usdc", Decimal("1000"))

    # 1000 input (300 cached, 700 non-cached), 0 output
    # non-cached: 1000 * 700 * 3 / 1_000_000   = 2.1
    # cached:     1000 * 300 * 0.3 / 1_000_000  = 0.09
    # total = 2.19
    cost = await model.calculate_cost(1000, 0, cached_input_tokens=300)
    assert cost == Decimal("2.1900")


@pytest.mark.asyncio
async def test_calculate_cost_fallback_when_no_cached_price(monkeypatch):
    """When cached_input_price is None, cached tokens are billed at input_price."""
    model = _make_model_info(cached_input_price=None)
    monkeypatch.setattr(llm_module, "credit_per_usdc", Decimal("1000"))

    cost_all_cached = await model.calculate_cost(1000, 0, cached_input_tokens=1000)
    cost_none_cached = await model.calculate_cost(1000, 0, cached_input_tokens=0)

    # Both should produce same result since fallback = input_price
    assert cost_all_cached == cost_none_cached


@pytest.mark.asyncio
async def test_calculate_cost_backward_compatible(monkeypatch):
    """calculate_cost without cached_input_tokens still works (default=0)."""
    model = _make_model_info()
    monkeypatch.setattr(llm_module, "credit_per_usdc", Decimal("1000"))

    cost = await model.calculate_cost(1000, 500)
    # Same as no_cached_tokens case
    assert cost == Decimal("10.5000")


@pytest.mark.asyncio
async def test_calculate_cost_cached_exceeds_input_clamps_to_zero(monkeypatch):
    """If cached_input_tokens > input_tokens, non-cached clamps to 0 (no negative)."""
    model = _make_model_info()
    monkeypatch.setattr(llm_module, "credit_per_usdc", Decimal("1000"))

    # Pass more cached than total input — should not go negative
    cost = await model.calculate_cost(100, 0, cached_input_tokens=200)
    # non-cached = max(100 - 200, 0) = 0
    # cached: 1000 * 100 * 0.3 / 1_000_000 = 0.03
    assert cost == Decimal("0.0300")


# ---------------------------------------------------------------------------
# CSV loading — cached_input_price parsed correctly
# ---------------------------------------------------------------------------


def test_csv_loads_cached_input_price_for_claude():
    """Claude Sonnet 4.6 should have cached_input_price=0.3 from CSV."""
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

    claude = models.get("openrouter:anthropic/claude-sonnet-4.6")
    assert claude is not None
    assert claude.cached_input_price == Decimal("0.3")
    assert claude.input_price == Decimal("3")


def test_csv_cached_input_price_none_for_deepseek():
    """DeepSeek V3.2 has no cached_input_price in CSV — should be None."""
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = None
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = "ds-test-key"
        mock_config.xai_api_key = None
        mock_config.openrouter_api_key = None
        mock_config.minimax_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None

        models = load_default_llm_models()

    deepseek = models.get("deepseek:deepseek-chat")
    assert deepseek is not None
    assert deepseek.cached_input_price is None


def test_csv_cached_input_price_for_grok4():
    """Grok 4.20 should have cached_input_price=0.2."""
    with patch("intentkit.models.llm.config") as mock_config:
        mock_config.openai_api_key = None
        mock_config.google_api_key = None
        mock_config.deepseek_api_key = None
        mock_config.xai_api_key = "xai-test-key"
        mock_config.openrouter_api_key = None
        mock_config.minimax_api_key = None
        mock_config.openai_compatible_api_key = None
        mock_config.openai_compatible_base_url = None
        mock_config.openai_compatible_model = None

        models = load_default_llm_models()

    grok4 = models.get("xai:grok-4.20-beta-0309-reasoning")
    assert grok4 is not None
    assert grok4.cached_input_price == Decimal("0.2")
