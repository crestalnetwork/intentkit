from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from intentkit.config.config import Config
from intentkit.models.llm import (
    LLMModelInfo,
    MiniMaxLLM,
    load_default_llm_models,
)


def _load_minimax_catalog() -> dict[str, LLMModelInfo]:
    configured = SimpleNamespace(
        openai_api_key=None,
        google_api_key=None,
        deepseek_api_key=None,
        xai_api_key=None,
        openrouter_api_key=None,
        minimax_plan_api_key="test-key",
        mimo_plan_api_key=None,
        openai_compatible_api_key=None,
        openai_compatible_base_url=None,
        openai_compatible_model=None,
        openai_compatible_model_lite=None,
        anthropic_compatible_api_key=None,
        anthropic_compatible_base_url=None,
        anthropic_compatible_model=None,
        anthropic_compatible_model_lite=None,
    )
    with patch("intentkit.models.llm.config", configured):
        return load_default_llm_models()


def test_minimax_catalog_covers_current_models_and_capabilities():
    models = _load_minimax_catalog()

    m3 = models["minimax:MiniMax-M3"]
    assert m3.context_length == 1_000_000
    assert m3.output_length == 512_000
    assert m3.input_price == Decimal("0.6")
    assert m3.cached_input_price == Decimal("0.12")
    assert m3.cache_write_price is None
    assert m3.output_price == Decimal("2.4")
    assert m3.supports_image_input is True
    assert m3.supports_video_input is True
    assert m3.thinking_modes == ["adaptive", "disabled"]
    assert m3.default_thinking_mode == "disabled"

    m27 = models["minimax:MiniMax-M2.7"]
    assert m27.context_length == 204_800
    assert m27.output_length == 204_800
    assert m27.supports_image_input is False
    assert m27.supports_video_input is False
    assert m27.thinking_modes == ["always_on"]
    assert m27.default_thinking_mode == "always_on"
    assert m27.cache_write_price == Decimal("0.375")


def test_minimax_m3_uses_target_pricing_for_costs():
    m3 = _load_minimax_catalog()["minimax:MiniMax-M3"]

    assert m3.cost_usd(600_000, 1_000_000) == Decimal("2.76")
    assert m3.cost_usd(
        600_000, 1_000_000, cached_input_tokens=100_000
    ) == Decimal("2.712")


def test_minimax_endpoint_examples_cover_both_regions_and_protocols():
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "https://api.minimax.io/anthropic" in env_example
    assert "https://api.minimaxi.com/anthropic" in env_example
    assert "https://api.minimax.io/v1" in env_example
    assert "https://api.minimaxi.com/v1" in env_example


def test_minimax_base_url_defaults_to_global_anthropic_endpoint(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.delenv("MINIMAX_PLAN_BASE_URL", raising=False)
    monkeypatch.setattr(Config, "_setup_langfuse", lambda self: None)

    cfg = Config()

    assert cfg.minimax_plan_base_url == "https://api.minimax.io/anthropic"


@pytest.mark.asyncio
async def test_minimax_adapter_uses_configured_anthropic_base_url(monkeypatch):
    m3 = _load_minimax_catalog()["minimax:MiniMax-M3"]
    captured: dict[str, object] = {}

    class FakeChatAnthropic:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    async def fake_get(model_id: str) -> LLMModelInfo:
        assert model_id == m3.id
        return m3

    monkeypatch.setattr("langchain_anthropic.ChatAnthropic", FakeChatAnthropic)
    monkeypatch.setattr(LLMModelInfo, "get", staticmethod(fake_get))
    monkeypatch.setattr("intentkit.models.llm.config.minimax_plan_api_key", "test-key")
    monkeypatch.setattr(
        "intentkit.models.llm.config.minimax_plan_base_url",
        "https://api.minimaxi.com/anthropic",
    )

    model = MiniMaxLLM(model_name=m3.id, info=m3)
    await model.create_instance()

    assert captured["base_url"] == "https://api.minimaxi.com/anthropic"
    assert captured["model"] == "MiniMax-M3"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    ["https://api.minimax.io/anthropic", "https://api.minimaxi.com/anthropic"],
)
async def test_anthropic_client_appends_messages_path(base_url):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "MiniMax-M3",
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)
    with patch(
        "langchain_anthropic.chat_models._get_default_async_httpx_client",
        return_value=async_client,
    ):
        model = ChatAnthropic.model_validate(
            {
                "model": "MiniMax-M3",
                "api_key": "test-key",
                "base_url": base_url,
                "max_retries": 0,
            }
        )

        try:
            await model.ainvoke("hello")
        finally:
            await async_client.aclose()

    assert requests[-1].url.path == "/anthropic/v1/messages"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url", ["https://api.minimax.io/v1", "https://api.minimaxi.com/v1"]
)
async def test_openai_client_appends_chat_completions_path(base_url):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
                "object": "chat.completion",
                "created": 0,
                "model": "MiniMax-M3",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport)
    sync_client = httpx.Client(transport=transport)
    model = ChatOpenAI(
        model="MiniMax-M3",
        api_key=SecretStr("test-key"),
        base_url=base_url,
        http_async_client=async_client,
        http_client=sync_client,
        max_retries=0,
    )

    try:
        await model.ainvoke("hello")
    finally:
        await async_client.aclose()
        sync_client.close()

    assert requests[-1].url.path == "/v1/chat/completions"
