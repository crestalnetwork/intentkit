"""Tests for USD cost pricing used by Langfuse cost forwarding."""

from decimal import Decimal
from types import SimpleNamespace

import intentkit.models.llm as llm_module
from intentkit.models.llm import LLMModelInfo, _resolve_generation_cost


def _info(input_price="0.5", cached: str | None = "0.05", output="3"):
    return LLMModelInfo.model_construct(
        input_price=Decimal(input_price),
        cached_input_price=Decimal(cached) if cached is not None else None,
        output_price=Decimal(output),
    )


def test_cost_usd_basic():
    # 1M input + 1M output at $0.5 / $3 per 1M
    assert _info().cost_usd(1_000_000, 1_000_000) == Decimal("3.5")


def test_cost_usd_prices_cached_at_cached_rate():
    # 1M input of which 500k cached: 500k*$0.5 + 500k*$0.05 + 1M*$3, per 1M
    cost = _info().cost_usd(1_000_000, 1_000_000, cached_input_tokens=500_000)
    assert cost == Decimal("0.25") + Decimal("0.025") + Decimal("3")


def test_cost_usd_falls_back_to_input_price_when_no_cached_price():
    # cached priced at input rate when no cached_input_price is set
    cost = _info(cached=None).cost_usd(1_000_000, 0, cached_input_tokens=1_000_000)
    assert cost == Decimal("0.5")


def test_cost_usd_clamps_cached_to_input():
    # cached can't exceed input; negatives clamped to 0
    assert _info().cost_usd(1000, 0, cached_input_tokens=999_999) == _info().cost_usd(
        1000, 0, cached_input_tokens=1000
    )


def _response(*, response_metadata=None, usage_metadata=None):
    message = SimpleNamespace(
        response_metadata=response_metadata or {},
        usage_metadata=usage_metadata,
    )
    return SimpleNamespace(generations=[[SimpleNamespace(message=message)]])


def test_resolve_prefers_provider_cost():
    # OpenRouter surfaces the real charge in response_metadata["cost"]
    resp = _response(response_metadata={"cost": 0.0034}, usage_metadata={"x": 1})
    assert _resolve_generation_cost(resp) == 0.0034


def test_resolve_falls_back_to_catalog_price(monkeypatch):
    monkeypatch.setattr(llm_module, "AVAILABLE_MODELS", {"k": _info()})
    monkeypatch.setattr(llm_module, "_MODEL_ID_INDEX", {"test-model": ["k"]})
    resp = _response(
        response_metadata={"model_name": "test-model"},
        usage_metadata={
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "input_token_details": {"cache_read": 500_000},
        },
    )
    # 500k*$0.5 + 500k*$0.05 + 1M*$3 = 3.275
    assert _resolve_generation_cost(resp) == 3.275


def test_resolve_strips_models_prefix(monkeypatch):
    monkeypatch.setattr(llm_module, "AVAILABLE_MODELS", {"k": _info()})
    monkeypatch.setattr(llm_module, "_MODEL_ID_INDEX", {"gemini-x": ["k"]})
    resp = _response(
        response_metadata={"model_name": "models/gemini-x"},
        usage_metadata={"input_tokens": 1_000_000, "output_tokens": 0},
    )
    assert _resolve_generation_cost(resp) == 0.5


def test_resolve_returns_none_when_unknown_model(monkeypatch):
    monkeypatch.setattr(llm_module, "_MODEL_ID_INDEX", {})
    resp = _response(
        response_metadata={"model_name": "nope"},
        usage_metadata={"input_tokens": 10, "output_tokens": 10},
    )
    assert _resolve_generation_cost(resp) is None


def test_resolve_returns_none_without_usage_or_cost():
    assert _resolve_generation_cost(_response()) is None
