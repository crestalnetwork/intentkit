"""Tests for music generation tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.tools.base import ToolException
from pydantic import ValidationError

from intentkit.tools.music import available, get_tools
from intentkit.tools.music.minimax import (
    MiniMaxMusicGeneration,
    MiniMaxMusicGenerationInput,
)


def test_input_schema_validates_conditional_fields():
    instrumental = MiniMaxMusicGenerationInput(
        prompt="ambient piano", is_instrumental=True
    )
    assert instrumental.model == "music-3.0"
    assert instrumental.output_format == "url"

    optimized = MiniMaxMusicGenerationInput(prompt="upbeat pop", lyrics_optimizer=True)
    assert optimized.lyrics is None

    with pytest.raises(ValidationError, match="requires lyrics"):
        MiniMaxMusicGenerationInput()
    with pytest.raises(ValidationError, match="China region"):
        MiniMaxMusicGenerationInput(
            prompt="ambient piano",
            is_instrumental=True,
            aigc_watermark=True,
        )
    with pytest.raises(ValidationError, match="hex output"):
        MiniMaxMusicGenerationInput(
            prompt="ambient piano", is_instrumental=True, stream=True
        )


@pytest.mark.asyncio
async def test_get_tools_selects_by_name():
    tools = await get_tools(["music_minimax_generate", "music_unknown"])
    assert [tool.name for tool in tools] == ["music_minimax_generate"]
    assert await get_tools([]) == []


def test_available_uses_configured_key():
    with patch("intentkit.tools.music.system_config") as config:
        config.minimax_plan_api_key = "test-key"
        assert available() is True
        config.minimax_plan_api_key = None
        assert available() is False


@pytest.mark.asyncio
async def test_generation_uses_global_endpoint_and_parses_url():
    response = MagicMock()
    response.json.return_value = {
        "base_resp": {"status_code": 0},
        "data": {"status": 2, "audio": "https://example.test/song.mp3"},
    }
    client = AsyncMock()
    client.post.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = client

    with (
        patch("intentkit.tools.music.base.config") as config,
        patch("intentkit.tools.music.minimax.httpx.AsyncClient", return_value=context),
    ):
        config.minimax_plan_api_key = "test-key"
        result = await MiniMaxMusicGeneration()._arun(
            prompt="ambient piano", is_instrumental=True
        )

    assert result == {
        "status": 2,
        "output_format": "url",
        "audio_url": "https://example.test/song.mp3",
        "url_ttl_hours": 24,
    }
    call = client.post.call_args
    assert call.args[0] == "https://api.minimax.io/v1/music_generation"
    assert call.kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert call.kwargs["json"]["model"] == "music-3.0"
    assert call.kwargs["json"]["audio_setting"] == {
        "sample_rate": 44100,
        "bitrate": 256000,
        "format": "mp3",
    }


@pytest.mark.asyncio
async def test_generation_uses_china_endpoint_and_watermark():
    response = MagicMock()
    response.json.return_value = {
        "base_resp": {"status_code": 0},
        "data": {"status": 2, "audio": "494433"},
    }
    client = AsyncMock()
    client.post.return_value = response
    context = AsyncMock()
    context.__aenter__.return_value = client

    with (
        patch("intentkit.tools.music.base.config") as config,
        patch("intentkit.tools.music.minimax.httpx.AsyncClient", return_value=context),
    ):
        config.minimax_plan_api_key = "test-key"
        result = await MiniMaxMusicGeneration()._arun(
            prompt="ambient piano",
            is_instrumental=True,
            region="cn_zh",
            aigc_watermark=True,
            output_format="hex",
        )

    assert result["audio_hex"] == "494433"
    call = client.post.call_args
    assert call.args[0] == "https://api.minimaxi.com/v1/music_generation"
    assert call.kwargs["json"]["aigc_watermark"] is True


def test_api_errors_raise_tool_exception():
    from intentkit.tools.music.minimax import _parse_payload

    with pytest.raises(ToolException, match="insufficient balance"):
        _parse_payload(
            {
                "base_resp": {
                    "status_code": 1008,
                    "status_msg": "insufficient balance",
                }
            }
        )
