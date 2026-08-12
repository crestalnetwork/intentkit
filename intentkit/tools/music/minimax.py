"""MiniMax music generation tool."""

import json
from typing import Any, Literal

import httpx
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field, model_validator

from intentkit.tools.music.base import MusicBaseTool

_ENDPOINTS = {
    "global_en": "https://api.minimax.io/v1/music_generation",
    "cn_zh": "https://api.minimaxi.com/v1/music_generation",
}

MusicModel = Literal[
    "music-3.0",
    "music-2.6",
    "music-3.0-free",
    "music-2.6-free",
]
MusicRegion = Literal["global_en", "cn_zh"]
MusicOutputFormat = Literal["url", "hex"]
MusicAudioFormat = Literal["mp3", "wav", "pcm"]


class MusicAudioSetting(BaseModel):
    """Audio encoding options for generated music."""

    sample_rate: Literal[16000, 24000, 32000, 44100] = 44100
    bitrate: Literal[32000, 64000, 128000, 256000] = 256000
    format: MusicAudioFormat = "mp3"


class MiniMaxMusicGenerationInput(BaseModel):
    """Input schema for text-to-music generation."""

    model: MusicModel = Field(default="music-3.0", description="Generation model")
    prompt: str | None = Field(
        default=None,
        max_length=2000,
        description="Music style, mood, and scenario",
    )
    lyrics: str | None = Field(
        default=None,
        min_length=1,
        max_length=3500,
        description="Song lyrics with newline-separated sections",
    )
    stream: bool = Field(default=False, description="Stream hex audio chunks")
    output_format: MusicOutputFormat = Field(
        default="url",
        description="Return a 24-hour URL or hex-encoded audio",
    )
    audio_setting: MusicAudioSetting = Field(default_factory=MusicAudioSetting)
    lyrics_optimizer: bool = Field(
        default=False,
        description="Generate lyrics from the prompt when lyrics are omitted",
    )
    is_instrumental: bool = Field(
        default=False,
        description="Generate music without vocals",
    )
    region: MusicRegion = Field(
        default="global_en",
        description="Use the global or China API endpoint",
    )
    aigc_watermark: bool | None = Field(
        default=None,
        description="Append the China-region audio watermark",
    )

    @model_validator(mode="after")
    def validate_generation_options(self):
        """Validate conditional API requirements."""
        if self.stream and self.output_format != "hex":
            raise ValueError("streaming requires hex output")
        if self.region != "cn_zh" and self.aigc_watermark is not None:
            raise ValueError("aigc_watermark is only available in the China region")
        if self.is_instrumental and not self.prompt:
            raise ValueError("instrumental generation requires a prompt")
        if not self.is_instrumental and not self.lyrics and not self.lyrics_optimizer:
            raise ValueError("vocal generation requires lyrics or lyrics optimization")
        if self.lyrics_optimizer and not self.prompt:
            raise ValueError("lyrics optimization requires a prompt")
        return self


def _parse_payload(payload: dict[str, Any]) -> tuple[str, int]:
    """Validate a response payload and return its audio and status."""
    base_response = payload.get("base_resp") or {}
    if base_response.get("status_code") != 0:
        message = base_response.get("status_msg") or "unknown API error"
        raise ToolException(f"Music generation failed: {message}")

    data = payload.get("data") or {}
    status = data.get("status")
    audio = data.get("audio")
    if status not in (1, 2) or not isinstance(audio, str) or not audio:
        raise ToolException("Music generation returned no audio")
    return audio, status


class MiniMaxMusicGeneration(MusicBaseTool):
    """Generate music using MiniMax Music models."""

    name: str = "music_minimax_generate"
    title: str = "MiniMax Music Generation"
    description: str = (
        "Generate instrumental or vocal music from a prompt and optional lyrics. "
        "Supports global and China endpoints, URL or hex output, MP3, WAV, and PCM."
    )
    args_schema: ArgsSchema | None = MiniMaxMusicGenerationInput

    async def _arun(
        self,
        model: MusicModel = "music-3.0",
        prompt: str | None = None,
        lyrics: str | None = None,
        stream: bool = False,
        output_format: MusicOutputFormat = "url",
        audio_setting: MusicAudioSetting | dict[str, Any] | None = None,
        lyrics_optimizer: bool = False,
        is_instrumental: bool = False,
        region: MusicRegion = "global_en",
        aigc_watermark: bool | None = None,
        **_,
    ) -> dict[str, Any]:
        """Generate music and parse the completed audio response."""
        settings = MusicAudioSetting.model_validate(audio_setting or {})
        body: dict[str, Any] = {
            "model": model,
            "stream": stream,
            "output_format": output_format,
            "audio_setting": settings.model_dump(),
            "lyrics_optimizer": lyrics_optimizer,
            "is_instrumental": is_instrumental,
        }
        if prompt is not None:
            body["prompt"] = prompt
        if lyrics is not None:
            body["lyrics"] = lyrics
        if region == "cn_zh" and aigc_watermark is not None:
            body["aigc_watermark"] = aigc_watermark

        headers = {
            "Authorization": f"Bearer {self.get_api_key()}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                if not stream:
                    response = await client.post(
                        _ENDPOINTS[region], json=body, headers=headers
                    )
                    response.raise_for_status()
                    audio, status = _parse_payload(response.json())
                else:
                    chunks: list[str] = []
                    status = 1
                    async with client.stream(
                        "POST", _ENDPOINTS[region], json=body, headers=headers
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            line = line.removeprefix("data:").strip()
                            if not line or line == "[DONE]":
                                continue
                            chunk, status = _parse_payload(json.loads(line))
                            chunks.append(chunk)
                    audio = "".join(chunks)
                    if not audio:
                        raise ToolException("Music generation returned no audio")

            return {
                "status": status,
                "output_format": output_format,
                "audio_url" if output_format == "url" else "audio_hex": audio,
                "url_ttl_hours": 24 if output_format == "url" else None,
            }
        except ToolException:
            raise
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            raise ToolException(f"Music generation API error: {error}") from error
