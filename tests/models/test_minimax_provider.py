"""MiniMax rollout contracts at the real LangChain/SDK HTTP boundary (offline)."""

import json
from decimal import Decimal
from unittest.mock import patch

import httpx
import httpx2
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from intentkit.config.config import Config
from intentkit.models import llm, llm_picker


@pytest.fixture
def catalog(monkeypatch):
    monkeypatch.setattr(llm.config, "minimax_plan_api_key", "test-minimax-key")
    monkeypatch.setattr(llm.config, "openrouter_api_key", "test-openrouter-key")
    monkeypatch.setattr(
        llm.config, "minimax_base_url", "https://api.minimax.io/anthropic"
    )
    models = llm.load_default_llm_models()
    monkeypatch.setattr(llm, "AVAILABLE_MODELS", models)
    monkeypatch.setattr(llm, "_MODEL_ID_INDEX", llm.build_model_id_index(models))
    monkeypatch.setattr(llm_picker, "AVAILABLE_MODELS", models)
    return models


@pytest.fixture
def wire(monkeypatch):
    """Intercept only HTTP sends; model construction and serialization stay real."""
    requests = []

    def install(module):
        async def send(self, request, **kwargs):
            body = json.loads(request.content)
            requests.append((str(request.url), body))
            if request.url.path.endswith("/messages"):
                response = {
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "model": body["model"],
                    "content": [{"type": "text", "text": "ok"}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            else:
                response = {
                    "id": "chatcmpl_test",
                    "object": "chat.completion",
                    "system_fingerprint": None,
                    "created": 0,
                    "model": body["model"],
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
                }
            return module.Response(200, json=response, request=request)

        monkeypatch.setattr(module.AsyncClient, "send", send)

    install(httpx)
    install(httpx2)
    return requests


def test_catalog_prices_capabilities_and_order(catalog):
    direct = [
        m
        for m in catalog.values()
        if m.provider == llm.LLMProvider.MINIMAX and m.selectable
    ]
    assert [m.api_id for m in direct] == ["MiniMax-M3.1-Flash", "MiniMax-M3"]
    flash = direct[0]
    assert (flash.context_length, flash.output_length) == (1_000_000, 524_288)
    assert (flash.input_price, flash.output_price, flash.cached_input_price) == (
        Decimal("0.15"),
        Decimal("0.60"),
        Decimal("0.015"),
    )
    assert flash.supports_image_input and flash.supports_video_input
    assert not flash.supports_audio_input
    assert flash.cost_usd(1_000_000, 1_000_000, 100_000) == Decimal("0.7365")
    gateway = [
        m
        for m in catalog.values()
        if m.provider == llm.LLMProvider.OPENROUTER
        and m.id.startswith("minimax/")
        and m.selectable
    ]
    assert [m.api_id for m in gateway] == [
        "minimax/minimax-m3.1-flash:free",
        "minimax/minimax-m3",
    ]
    assert gateway[0].input_price == gateway[0].output_price == 0
    assert gateway[0].origin_provider == "minimax"
    # Preserve the pinned gateway M3 contract rather than copying direct limits.
    assert (gateway[1].context_length, gateway[1].output_length) == (524_288, 512_000)
    assert gateway[1].origin_provider == "minimax/fp8"


@pytest.mark.asyncio
async def test_hidden_legacy_remains_explicitly_routable(catalog):
    choices = llm_picker.list_available_model_ids()
    assert choices.index("minimax-flash") < choices.index("minimax")
    assert choices.index("minimax/minimax-flash:free") < choices.index(
        "minimax/minimax"
    )
    for model_id in ("MiniMax-M2.7", "minimax/minimax-m2-her"):
        assert model_id not in choices
        assert model_id not in [m.id for m in await llm.LLMModelInfo.get_all()]
        assert (await llm.LLMModelInfo.get(model_id)).api_id == model_id
        assert llm.resolve_model_id(model_id) == model_id
    assert (await llm.LLMModelInfo.get("minimax")).api_id == "MiniMax-M3"
    assert (await llm.LLMModelInfo.get("MiniMax-M3")).api_id == "MiniMax-M3"
    assert (
        await llm.LLMModelInfo.get("minimax/minimax")
    ).api_id == "minimax/minimax-m3"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider", [llm.LLMProvider.MINIMAX, llm.LLMProvider.OPENROUTER]
)
async def test_default_picker_reaches_real_sdk(catalog, wire, provider):
    with patch.object(
        llm.LLMProvider, "is_configured", property(lambda self: self == provider)
    ):
        selected = llm_picker.pick_default_model()
    adapter = await llm.create_llm_model(selected)
    model = await adapter.create_instance()
    await model.ainvoke("hello")
    url, body = wire[-1]
    assert "service_tier" not in body
    if provider == llm.LLMProvider.MINIMAX:
        assert url == "https://api.minimax.io/anthropic/v1/messages"
        assert body["model"] == "MiniMax-M3.1-Flash"
        assert body["thinking"] == {"type": "adaptive"}
        assert body["output_config"] == {"effort": "max"}
    else:
        assert url == "https://openrouter.ai/api/v1/chat/completions"
        assert body["model"] == "minimax/minimax-m3.1-flash:free"
        assert body["reasoning"] == {"effort": "max"}
        assert body["provider"] == {"order": ["minimax"], "allow_fallbacks": False}


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
async def test_flash_effort_at_http_boundary(catalog, wire, effort):
    adapter = await llm.create_llm_model("MiniMax-M3.1-Flash", effort)
    model = await adapter.create_instance()
    await model.ainvoke("hello")
    assert wire[-1][1]["output_config"] == {"effort": effort}
    assert wire[-1][1]["thinking"] == {"type": "adaptive"}


@pytest.mark.asyncio
@pytest.mark.parametrize("effort", ["none", "minimal"])
@pytest.mark.parametrize("model_id", ["minimax-flash", "minimax/minimax-flash:free"])
async def test_flash_rejects_unsupported_effort_before_http(
    catalog, wire, effort, model_id
):
    adapter = await llm.create_llm_model(model_id, effort)
    with pytest.raises(ValueError, match="requires low/medium/high/xhigh/max"):
        await adapter.create_instance()
    assert wire == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_id", ["minimax", "MiniMax-M3", "minimax:MiniMax-M3", "MiniMax-M2.7"]
)
@pytest.mark.parametrize("effort", [None, "none", "high"])
async def test_saved_models_keep_wire_id_and_no_effort_depth(
    catalog, wire, model_id, effort
):
    adapter = await llm.create_llm_model(model_id, effort)
    model = await adapter.create_instance()
    await model.ainvoke("hello")
    body = wire[-1][1]
    assert body["model"] == (
        "MiniMax-M2.7" if model_id == "MiniMax-M2.7" else "MiniMax-M3"
    )
    assert "output_config" not in body
    if model_id == "MiniMax-M2.7":
        assert "thinking" not in body
    elif effort == "none":
        assert body["thinking"] == {"type": "disabled"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    [
        "https://api.minimax.io/anthropic",
        "https://api.minimaxi.com/anthropic",
        "https://custom.example/anthropic",
    ],
)
async def test_configured_endpoint_tools_images_and_reasoning_history(
    catalog, wire, monkeypatch, base_url
):
    # Endpoint preservation is tested offline; this does not claim regional entitlement.
    monkeypatch.setattr(llm.config, "minimax_base_url", base_url)
    adapter = await llm.create_llm_model("minimax-flash")
    model = await adapter.create_instance()
    tool = {
        "name": "lookup",
        "description": "Look up a value",
        "input_schema": {"type": "object", "properties": {}},
    }
    thinking = {
        "type": "thinking",
        "thinking": "Keep this reasoning.",
        "signature": "test-signature",
    }
    image = {
        "type": "image",
        "source": {"type": "url", "url": "https://example.com/image.png"},
    }
    history = [
        HumanMessage(content=[{"type": "text", "text": "Read this"}, image]),
        AIMessage(
            content=[
                thinking,
                {"type": "tool_use", "id": "call_test", "name": "lookup", "input": {}},
            ]
        ),
        ToolMessage(content="found", tool_call_id="call_test"),
    ]
    await model.bind_tools([tool]).ainvoke(history)
    url, body = wire[-1]
    assert url == base_url + "/v1/messages"
    assert body["tools"][0]["name"] == "lookup"
    assert body["messages"][0]["content"][1] == image
    assert body["messages"][1]["content"][0] == thinking
    assert body["messages"][1]["content"][1]["id"] == "call_test"
    assert body["messages"][2]["content"][0]["tool_use_id"] == "call_test"


@pytest.mark.asyncio
async def test_gateway_tools_images_and_reasoning_history(catalog, wire):
    adapter = await llm.create_llm_model("minimax/minimax-flash:free")
    model = await adapter.create_instance()
    details = [{"type": "reasoning.text", "text": "Keep reasoning", "index": 0}]
    image = {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}
    history = [
        HumanMessage(content=[{"type": "text", "text": "Read this"}, image]),
        AIMessage(
            content="",
            additional_kwargs={"reasoning_details": details},
            tool_calls=[{"id": "call_test", "name": "lookup", "args": {}}],
        ),
        ToolMessage(content="found", tool_call_id="call_test"),
    ]
    tool = {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Look up",
            "parameters": {"type": "object", "properties": {}},
        },
    }
    await model.bind_tools([tool]).ainvoke(history)
    body = wire[-1][1]
    assert body["messages"][0]["content"][1] == image
    assert body["messages"][1]["reasoning_details"] == details
    assert body["messages"][1]["tool_calls"][0]["id"] == "call_test"
    assert body["messages"][2]["tool_call_id"] == "call_test"
    assert body["tools"][0]["function"]["name"] == "lookup"


@pytest.mark.asyncio
@pytest.mark.parametrize("model_id", ["minimax/minimax", "minimax/minimax-m2-her"])
async def test_saved_gateway_wire_ids(catalog, wire, model_id):
    adapter = await llm.create_llm_model(model_id)
    model = await adapter.create_instance()
    await model.ainvoke("hello")
    expected = "minimax/minimax-m3" if model_id == "minimax/minimax" else model_id
    assert wire[-1][1]["model"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
async def test_custom_compatible_model_preserved(catalog, wire, monkeypatch, protocol):
    prefix = protocol + "_compatible"
    base_url = "https://custom.example/" + (
        "v1" if protocol == "openai" else "anthropic"
    )
    for suffix, value in (
        ("api_key", "test-custom-key"),
        ("base_url", base_url),
        ("model", "MiniMax-private-saved"),
    ):
        monkeypatch.setattr(llm.config, prefix + "_" + suffix, value)
    models = llm.load_default_llm_models()
    monkeypatch.setattr(llm, "AVAILABLE_MODELS", models)
    monkeypatch.setattr(llm, "_MODEL_ID_INDEX", llm.build_model_id_index(models))
    adapter = await llm.create_llm_model("MiniMax-private-saved")
    model = await adapter.create_instance()
    await model.ainvoke("hello")
    url, body = wire[-1]
    assert url == base_url + (
        "/chat/completions" if protocol == "openai" else "/v1/messages"
    )
    assert body["model"] == "MiniMax-private-saved"
    assert "output_config" not in body


@pytest.mark.parametrize("legacy", [True, False])
def test_config_aliases_preserve_endpoint_and_key(monkeypatch, legacy):
    monkeypatch.setenv("REDIS_HOST", "localhost")
    for key in (
        "MINIMAX_API_KEY",
        "MINIMAX_BASE_URL",
        "MINIMAX_PLAN_API_KEY",
        "MINIMAX_PLAN_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    prefix = "MINIMAX_PLAN" if legacy else "MINIMAX"
    monkeypatch.setenv(prefix + "_API_KEY", "test-config-key")
    monkeypatch.setenv(prefix + "_BASE_URL", "https://custom.example/anthropic")
    monkeypatch.setattr(Config, "_setup_langfuse", lambda self: None)
    cfg = Config()
    assert cfg.minimax_plan_api_key == "test-config-key"
    assert cfg.minimax_base_url == "https://custom.example/anthropic"
