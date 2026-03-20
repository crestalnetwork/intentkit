"""Base class for image generation skills."""

import base64
import logging
from abc import ABCMeta, abstractmethod
from typing import Any, Literal, override

import httpx
from epyxid import XID
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.clients.s3 import get_cdn_url, store_image_bytes
from intentkit.config.config import config
from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType
from intentkit.skills.base import IntentKitSkill

logger = logging.getLogger(__name__)


class ImageGenerationInput(BaseModel):
    """Input for image generation skills."""

    prompt: str = Field(description="Image description prompt")
    images: list[str] | None = Field(
        default=None,
        description="Optional list of input image URLs for editing/reference",
    )


class ImageBaseTool(IntentKitSkill, metaclass=ABCMeta):
    """Base class for all image generation skills.

    Provides shared logic for OpenRouter fallback, image downloading,
    S3 upload, and attachment building.
    """

    category: str = "image"
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    args_schema: ArgsSchema | None = ImageGenerationInput

    # Subclasses set these
    native_model: str = ""
    openrouter_model: str = ""

    @abstractmethod
    def _has_native_key(self) -> bool:
        """Return True if the native API key is configured."""
        ...

    @abstractmethod
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        """Generate image using native API. Return raw image bytes."""
        ...

    async def _download_images(self, urls: list[str]) -> list[bytes]:
        """Download images from URLs and return as bytes."""
        results: list[bytes] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for url in urls:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                results.append(resp.content)
        return results

    async def _generate_via_openrouter(
        self, prompt: str, images: list[bytes] | None
    ) -> bytes:
        """Generate image via OpenRouter chat completions API."""
        key = config.openrouter_api_key
        if not key:
            raise ToolException("OpenRouter API key is not configured")

        # Build message content
        content: list[dict[str, Any]]
        if images:
            content = [{"type": "text", "text": prompt}]
            for img in images:
                b64 = base64.b64encode(img).decode()
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                )
        else:
            content = [{"type": "text", "text": prompt}]

        payload = {
            "model": self.openrouter_model,
            "messages": [{"role": "user", "content": content}],
            "modalities": ["image", "text"],
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
            )
            resp.raise_for_status()
            data = resp.json()

        # Extract image from response
        try:
            message = data["choices"][0]["message"]
            # OpenRouter returns images in message.images array
            if "images" in message and message["images"]:
                image_url = message["images"][0]["image_url"]["url"]
                # data:image/png;base64,...
                if image_url.startswith("data:"):
                    b64_data = image_url.split(",", 1)[1]
                    return base64.b64decode(b64_data)
                # Direct URL - download it
                async with httpx.AsyncClient(timeout=30) as client:
                    img_resp = await client.get(image_url, follow_redirects=True)
                    img_resp.raise_for_status()
                    return img_resp.content

            # Fallback: check content parts for image data
            if "content" in message:
                for part in (
                    message["content"] if isinstance(message["content"], list) else []
                ):
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        url = part["image_url"]["url"]
                        if url.startswith("data:"):
                            b64_data = url.split(",", 1)[1]
                            return base64.b64decode(b64_data)
                        async with httpx.AsyncClient(timeout=30) as client:
                            img_resp = await client.get(url, follow_redirects=True)
                            img_resp.raise_for_status()
                            return img_resp.content
        except (KeyError, IndexError) as e:
            raise ToolException(f"Failed to parse OpenRouter image response: {e}")

        raise ToolException("No image found in OpenRouter response")

    async def _upload_and_return(
        self, image_bytes: bytes, context: Any, skill_name: str
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Upload image to S3 and return text + attachment tuple."""
        job_id = str(XID())
        image_key = f"{context.agent_id}/image/{skill_name}/{job_id}"
        stored_path = await store_image_bytes(image_bytes, image_key)
        if not stored_path:
            raise ToolException("Failed to store image: S3 storage not configured")
        url = get_cdn_url(stored_path)

        attachment: ChatMessageAttachment = {
            "type": ChatMessageAttachmentType.IMAGE,
            "lead_text": None,
            "url": url,
            "json": None,
        }
        return f"Image generated successfully: {url}", [attachment]

    @override
    async def _arun(
        self,
        prompt: str,
        images: list[str] | None = None,
        **kwargs: Any,
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Orchestrate image generation: key check -> generate -> upload -> return."""
        context = self.get_context()

        try:
            # Download input images if provided
            input_images: list[bytes] | None = None
            if images:
                input_images = await self._download_images(images)

            # Try native API first, fall back to OpenRouter
            if self._has_native_key():
                image_bytes = await self._generate_native(prompt, input_images)
            elif config.openrouter_api_key and self.openrouter_model:
                image_bytes = await self._generate_via_openrouter(prompt, input_images)
            else:
                raise ToolException(
                    f"No API key configured for {self.name}. "
                    "Need native provider key or OpenRouter key."
                )

            return await self._upload_and_return(image_bytes, context, self.name)

        except ToolException:
            raise
        except httpx.HTTPStatusError as e:
            raise ToolException(
                f"API request failed: {e.response.status_code} {e.response.text[:200]}"
            )
        except Exception as e:
            raise ToolException(f"Error generating image with {self.name}: {e}")
