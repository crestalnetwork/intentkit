"""Google Veo video generation skills."""

import asyncio
import logging
from decimal import Decimal
from typing import override

import filetype
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.video.base import MAX_POLL_TIME, POLL_INTERVAL, VideoBaseTool

logger = logging.getLogger(__name__)


class VeoVideoBase(VideoBaseTool):
    """Base class for Google Veo video generation skills."""

    @override
    def _has_native_key(self) -> bool:
        return bool(config.google_api_key)

    @override
    async def _generate_native(self, prompt: str, image: bytes | None) -> bytes:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=config.google_api_key)

            # Build the generation config
            generate_config = types.GenerateVideosConfig(
                person_generation="allow_all",
            )

            if image:
                # Image-to-video: detect mime type and pass as reference
                kind = filetype.guess(image)
                mime_type = kind.mime if kind else "image/png"
                genai_image = types.Image(image_bytes=image, mime_type=mime_type)
                operation = client.models.generate_videos(
                    model=self.native_model,
                    prompt=prompt,
                    image=genai_image,
                    config=generate_config,
                )
            else:
                # Text-to-video
                operation = client.models.generate_videos(
                    model=self.native_model,
                    prompt=prompt,
                    config=generate_config,
                )

            # Poll for completion
            elapsed = 0
            while not operation.done and elapsed < MAX_POLL_TIME:
                await asyncio.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
                operation = client.operations.get(operation)

            if not operation.done:
                raise ToolException(
                    f"Google Veo video generation timed out after {MAX_POLL_TIME} seconds"
                )

            if operation.error:
                error_msg = str(operation.error)
                raise ToolException(f"Google Veo video generation failed: {error_msg}")

            # Extract video from response
            result = operation.result
            if result and result.generated_videos:
                video = result.generated_videos[0].video
                if video and video.video_bytes:
                    return video.video_bytes

            raise ToolException("No video found in Google Veo response")
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Google Veo API error: {e}")


class VeoVideo(VeoVideoBase):
    """Generate videos using Google Veo 3.1."""

    name: str = "video_veo"
    description: str = (
        "Generate videos from text prompts or images using Google Veo 3.1. "
        "Highest quality with audio. Max 8 seconds, 1080p."
    )
    price: Decimal = Decimal("3200")
    native_model: str = "veo-3.1-generate-preview"


class VeoVideoFast(VeoVideoBase):
    """Generate videos using Google Veo 3.1 Fast."""

    name: str = "video_veo_fast"
    description: str = (
        "Generate videos from text prompts or images using Google Veo 3.1 Fast. "
        "Faster generation with audio. Max 8 seconds, 1080p."
    )
    price: Decimal = Decimal("1200")
    native_model: str = "veo-3.1-fast-generate-preview"
