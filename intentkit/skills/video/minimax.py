"""MiniMax Hailuo video generation skills."""

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

_MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class HailuoVideoBase(VideoBaseTool):
    """Base class for MiniMax Hailuo video generation skills."""

    @override
    def has_native_key(self) -> bool:
        return bool(config.minimax_api_key)

    @override
    async def _generate_native(self, prompt: str, image: bytes | None) -> bytes:
        headers = {
            "Authorization": f"Bearer {config.minimax_api_key}",
        }

        body: dict[str, object] = {
            "model": self.native_model,
            "prompt": prompt,
        }

        if image:
            b64 = base64.b64encode(image).decode()
            body["first_frame_image"] = f"data:image/png;base64,{b64}"

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # Step 1: Submit generation request
                resp = await client.post(
                    f"{_MINIMAX_BASE_URL}/video_generation",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                base_resp = data.get("base_resp", {})
                if base_resp.get("status_code", 0) != 0:
                    raise ToolException(
                        f"MiniMax video generation failed: {base_resp.get('status_msg', 'Unknown error')}"
                    )

                task_id = data.get("task_id")
                if not task_id:
                    raise ToolException("No task_id in MiniMax video response")

                # Step 2: Poll for completion
                elapsed = 0
                file_id = None
                while elapsed < MAX_POLL_TIME:
                    await asyncio.sleep(POLL_INTERVAL)
                    elapsed += POLL_INTERVAL

                    poll_resp = await client.get(
                        f"{_MINIMAX_BASE_URL}/query/video_generation",
                        params={"task_id": task_id},
                        headers=headers,
                    )
                    poll_resp.raise_for_status()
                    poll_data = poll_resp.json()

                    status = poll_data.get("status")
                    if status == "Success":
                        file_id = poll_data.get("file_id")
                        if not file_id:
                            raise ToolException(
                                "No file_id in completed MiniMax video response"
                            )
                        break
                    elif status == "Fail":
                        base_resp = poll_data.get("base_resp", {})
                        error_msg = base_resp.get("status_msg", "Unknown error")
                        raise ToolException(
                            f"MiniMax video generation failed: {error_msg}"
                        )

                if not file_id:
                    raise ToolException(
                        f"MiniMax video generation timed out after {MAX_POLL_TIME} seconds"
                    )

                # Step 3: Retrieve download URL
                file_resp = await client.get(
                    f"{_MINIMAX_BASE_URL}/files/retrieve",
                    params={"file_id": file_id},
                    headers=headers,
                )
                file_resp.raise_for_status()
                file_data = file_resp.json()

                file_obj = file_data.get("file", {})
                download_url = file_obj.get("download_url")
                if not download_url:
                    raise ToolException(
                        "No download_url in MiniMax file retrieve response"
                    )

                # Download the video
                video_resp = await client.get(
                    download_url, follow_redirects=True, timeout=120
                )
                video_resp.raise_for_status()
                if len(video_resp.content) > MAX_VIDEO_SIZE:
                    raise ToolException(
                        f"Video too large: {len(video_resp.content)} bytes"
                    )
                return video_resp.content
        except ToolException:
            raise
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            raise ToolException(f"MiniMax video API error: {e}")


class HailuoVideo(HailuoVideoBase):
    """Generate videos using MiniMax Hailuo 2.3."""

    name: str = "video_hailuo"
    description: str = (
        "Generate videos from text prompts or images using MiniMax Hailuo 2.3. "
        "Supports text-to-video and image-to-video. Max 10 seconds, up to 1080p."
    )
    price: Decimal = Decimal("500")
    native_model: str = "MiniMax-Hailuo-2.3"
