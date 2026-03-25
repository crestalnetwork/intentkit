"""Base class for video generation skills."""

import logging
from abc import ABCMeta, abstractmethod
from typing import Any, Literal, override

import httpx
from epyxid import XID
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.clients.s3 import FileType, get_cdn_url, store_file_bytes
from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType
from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)

# Shared polling constants for async video generation APIs
POLL_INTERVAL = 5  # seconds between status checks
MAX_POLL_TIME = 300  # 5 minutes max wait
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB


class VideoGenerationInput(BaseModel):
    """Input for video generation skills."""

    prompt: str = Field(description="Video description prompt")
    image: str | None = Field(
        default=None,
        description="Optional input image URL for image-to-video generation",
    )


class VideoBaseTool(IntentKitSkill, metaclass=ABCMeta):
    """Base class for all video generation skills.

    Provides shared logic for S3 upload and attachment building.
    All video APIs are async (submit job, poll for completion).
    """

    category: str = "video"
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    args_schema: ArgsSchema | None = VideoGenerationInput

    # Subclasses set these
    native_model: str = ""

    @override
    def available(self) -> bool:
        """Check if this video skill is available based on API keys."""
        return self.has_native_key()

    @abstractmethod
    def has_native_key(self) -> bool:
        """Return True if the native API key is configured."""
        ...

    @abstractmethod
    async def _generate_native(self, prompt: str, image: bytes | None) -> bytes:
        """Generate video using native API. Return raw video bytes (mp4)."""
        ...

    async def _download_image(self, url: str) -> bytes:
        """Download an image from URL and return as bytes."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp.content

    async def _upload_and_return(
        self, video_bytes: bytes, context: Any, skill_name: str
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Upload video to S3 and return text + attachment tuple."""
        job_id = str(XID())
        video_key = f"{context.agent_id}/video/{skill_name}/{job_id}"
        stored_path = await store_file_bytes(video_bytes, video_key, FileType.VIDEO)
        if not stored_path:
            raise ToolException("Failed to store video: S3 storage not configured")
        url = get_cdn_url(stored_path)

        attachment: ChatMessageAttachment = {
            "type": ChatMessageAttachmentType.VIDEO,
            "lead_text": None,
            "url": url,
            "json": None,
        }
        return f"Video generated successfully: {url}", [attachment]

    @override
    async def _arun(
        self,
        prompt: str,
        image: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Orchestrate video generation: key check -> generate -> upload -> return."""
        context = self.get_context()

        try:
            # Download input image if provided
            input_image: bytes | None = None
            if image:
                input_image = await self._download_image(image)

            if self.has_native_key():
                video_bytes = await self._generate_native(prompt, input_image)
            else:
                raise ToolException(
                    f"No API key configured for {self.name}. Need native provider key."
                )

            return await self._upload_and_return(video_bytes, context, self.name)

        except ToolException:
            raise
        except httpx.HTTPStatusError as e:
            raise ToolException(
                f"API request failed: {e.response.status_code} {e.response.text[:200]}"
            )
        except Exception as e:
            raise ToolException(f"Error generating video with {self.name}: {e}")
