"""Grok video generation skills using xAI API."""

import asyncio
import base64
import logging
from decimal import Decimal
from typing import override

import httpx
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.video.base import (
    MAX_POLL_TIME,
    MAX_VIDEO_SIZE,
    POLL_INTERVAL,
    VideoBaseTool,
)

logger = logging.getLogger(__name__)

_XAI_BASE_URL = "https://api.x.ai/v1"


class GrokVideoBase(VideoBaseTool):
    """Base class for Grok video generation skills."""

    @override
    def has_native_key(self) -> bool:
        return bool(config.xai_api_key)

    @override
    async def _generate_native(self, prompt: str, image: bytes | None) -> bytes:
        headers = {
            "Authorization": f"Bearer {config.xai_api_key}",
            "Content-Type": "application/json",
        }

        # Build request body
        body: dict[str, object] = {
            "model": self.native_model,
            "prompt": prompt,
        }

        if image:
            b64 = base64.b64encode(image).decode()
            body["image"] = {"type": "base64", "data": b64}

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # Submit generation request
                resp = await client.post(
                    f"{_XAI_BASE_URL}/videos/generations",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                request_id = data.get("request_id")
                if not request_id:
                    raise ToolException("No request_id in xAI video response")

                # Poll for completion
                elapsed = 0
                while elapsed < MAX_POLL_TIME:
                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL

                    poll_resp = await client.get(
                        f"{_XAI_BASE_URL}/videos/{request_id}",
                        headers=headers,
                    )
                    poll_resp.raise_for_status()
                    poll_data = poll_resp.json()

                    status = poll_data.get("status")
                    if status == "done":
                        video_obj = poll_data.get("video", {})
                        video_url = (
                            video_obj.get("url")
                            if isinstance(video_obj, dict)
                            else None
                        )
                        if not video_url:
                            raise ToolException(
                                "No video.url in completed xAI response"
                            )
                        # Download the video
                        video_resp = await client.get(
                            video_url, follow_redirects=True, timeout=120
                        )
                        video_resp.raise_for_status()
                        if len(video_resp.content) > MAX_VIDEO_SIZE:
                            raise ToolException(
                                f"Video too large: {len(video_resp.content)} bytes"
                            )
                        return video_resp.content
                    elif status == "failed":
                        error = poll_data.get("error", "Unknown error")
                        raise ToolException(f"xAI video generation failed: {error}")

                raise ToolException(
                    f"xAI video generation timed out after {MAX_POLL_TIME} seconds"
                )
        except ToolException:
            raise
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            raise ToolException(f"xAI video API error: {e}")


class GrokVideo(GrokVideoBase):
    """Generate videos using Grok Imagine Video."""

    name: str = "video_grok"
    description: str = (
        "Generate videos from text prompts or images using xAI Grok Imagine Video. "
        "Supports text-to-video and image-to-video. Max 15 seconds, 720p."
    )
    price: Decimal = Decimal("500")
    native_model: str = "grok-imagine-video"
