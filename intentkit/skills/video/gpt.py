"""OpenAI Sora video generation skills."""

import asyncio
import base64
import logging
from decimal import Decimal
from typing import override

import httpx
import openai
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.video.base import (
    MAX_POLL_TIME,
    MAX_VIDEO_SIZE,
    POLL_INTERVAL,
    VideoBaseTool,
)

logger = logging.getLogger(__name__)


class SoraVideoBase(VideoBaseTool):
    """Base class for OpenAI Sora video generation skills."""

    @override
    def _has_native_key(self) -> bool:
        return bool(config.openai_api_key)

    @override
    async def _generate_native(self, prompt: str, image: bytes | None) -> bytes:
        try:
            client = openai.OpenAI(api_key=config.openai_api_key)

            # Submit video generation
            if image:
                # Image-to-video via base64 data URL
                from openai.types.image_input_reference_param import (
                    ImageInputReferenceParam,
                )

                b64_data = base64.b64encode(image).decode()
                input_ref = ImageInputReferenceParam(
                    image_url=f"data:image/png;base64,{b64_data}",
                )
                video = client.videos.create(
                    model=self.native_model,
                    prompt=prompt,
                    input_reference=input_ref,
                )
            else:
                video = client.videos.create(
                    model=self.native_model,
                    prompt=prompt,
                )
            video_id = video.id
            if not video_id:
                raise ToolException("No id in OpenAI video response")

            # Poll for completion
            elapsed = 0
            while elapsed < MAX_POLL_TIME:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL

                video_status = client.videos.retrieve(video_id)
                status = video_status.status

                if status == "completed":
                    # Download the video content
                    async with httpx.AsyncClient(timeout=120) as http_client:
                        content_resp = await http_client.get(
                            f"https://api.openai.com/v1/videos/{video_id}/content",
                            headers={
                                "Authorization": f"Bearer {config.openai_api_key}",
                            },
                            follow_redirects=True,
                        )
                        content_resp.raise_for_status()
                        if len(content_resp.content) > MAX_VIDEO_SIZE:
                            raise ToolException(
                                f"Video too large: {len(content_resp.content)} bytes"
                            )
                        return content_resp.content
                elif status == "failed":
                    error = video_status.error
                    error_msg = error.message if error else "Unknown error"
                    raise ToolException(f"OpenAI video generation failed: {error_msg}")

            raise ToolException(
                f"OpenAI video generation timed out after {MAX_POLL_TIME} seconds"
            )
        except ToolException:
            raise
        except openai.OpenAIError as e:
            raise ToolException(f"OpenAI video API error: {e}")
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            raise ToolException(f"OpenAI video API error: {e}")


class SoraVideo(SoraVideoBase):
    """Generate videos using OpenAI Sora 2."""

    name: str = "video_sora"
    description: str = (
        "Generate videos from text prompts or images using OpenAI Sora 2. "
        "Good for rapid iteration. Max 20 seconds, 720p."
    )
    price: Decimal = Decimal("1000")
    native_model: str = "sora-2"


class SoraVideoPro(SoraVideoBase):
    """Generate videos using OpenAI Sora 2 Pro."""

    name: str = "video_sora_pro"
    description: str = (
        "Generate high-quality videos from text prompts or images using OpenAI Sora 2 Pro. "
        "Higher quality and more stable output. Max 20 seconds, up to 1080p."
    )
    price: Decimal = Decimal("3000")
    native_model: str = "sora-2-pro"
