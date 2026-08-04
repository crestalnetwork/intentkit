"""Base class for image generation tools."""

import base64
import logging
from abc import ABCMeta, abstractmethod
from typing import Any, Literal, override

import filetype
import httpx
import openrouter
from epyxid import XID
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.clients.s3 import get_cdn_url, store_image_bytes
from intentkit.config.config import config
from intentkit.models.chat import ChatMessageAttachment, ChatMessageAttachmentType
from intentkit.tools.base import IntentKitTool
from intentkit.utils.ssrf import httpx_request_guard

logger = logging.getLogger(__name__)


class ImageGenerationInput(BaseModel):
    """Input for image generation tools."""

    prompt: str = Field(description="Image description prompt")
    images: list[str] | None = Field(
        default=None,
        description="Optional list of input image URLs for editing/reference",
    )


class ImageBaseTool(IntentKitTool, metaclass=ABCMeta):
    """Base class for all image generation tools.

    Provides shared logic for OpenRouter fallback, image downloading,
    S3 upload, and attachment building.
    """

    category: str = "image"
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"
    args_schema: ArgsSchema | None = ImageGenerationInput

    # Subclasses set these
    native_model: str = ""
    openrouter_model: str = ""
    # OpenAI image models are served only by OpenRouter's dedicated images
    # endpoint; chat completions rejects them. Most other image models are
    # chat-only, so the images endpoint stays opt-in per tool.
    openrouter_images_api: bool = False

    @override
    def available(self) -> bool:
        """Check if this image tool is available based on API keys."""
        return self.has_native_key() or (
            bool(config.openrouter_api_key) and bool(self.openrouter_model)
        )

    @abstractmethod
    def has_native_key(self) -> bool:
        """Return True if the native API key is configured."""
        ...

    @abstractmethod
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        """Generate image using native API. Return raw image bytes."""
        ...

    async def _download_images(self, urls: list[str]) -> list[bytes]:
        """Download images from URLs and return as bytes.

        The URLs are a tool argument, so the client carries the SSRF guard.
        """
        results: list[bytes] = []
        async with httpx.AsyncClient(
            timeout=30, event_hooks={"request": [httpx_request_guard]}
        ) as client:
            for url in urls:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                results.append(resp.content)
        return results

    async def _generate_via_openrouter(
        self, prompt: str, images: list[bytes] | None
    ) -> bytes:
        """Generate image via OpenRouter.

        Uses the ``openrouter`` Python SDK so attribution headers and retry
        config stay consistent with the rest of the integration. Tools with
        ``openrouter_images_api`` set go to the dedicated images endpoint;
        the rest go through chat completions with image output modality.
        """
        key = config.openrouter_api_key
        if not key:
            raise ToolException("OpenRouter API key is not configured")

        client = openrouter.OpenRouter(
            api_key=key,
            http_referer="https://github.com/crestalnetwork/intentkit",
            x_open_router_title="IntentKit",
            x_open_router_categories="cloud-agent",
            timeout_ms=120_000,
        )
        if self.openrouter_images_api:
            return await self._openrouter_images_request(client, prompt, images)
        return await self._openrouter_chat_request(client, prompt, images)

    async def _openrouter_images_request(
        self, client: openrouter.OpenRouter, prompt: str, images: list[bytes] | None
    ) -> bytes:
        """Generate via the dedicated images endpoint (/api/v1/images)."""
        input_references = _image_references(images)
        try:
            response = await client.images.generate_async(
                model=self.openrouter_model,
                prompt=prompt,
                # None rather than an empty list when there are no references
                input_references=input_references or None,  # pyright: ignore[reportArgumentType]
            )
        except Exception as e:
            raise ToolException(f"OpenRouter request failed: {e}")

        if not response.data:
            raise ToolException("No image found in OpenRouter response")
        return base64.b64decode(response.data[0].b64_json)

    async def _openrouter_chat_request(
        self, client: openrouter.OpenRouter, prompt: str, images: list[bytes] | None
    ) -> bytes:
        """Generate via chat completions with image output modality."""
        content: list[dict[str, Any]] = [
            {"type": "text", "text": prompt},
            *_image_references(images),
        ]

        try:
            # Image-only OpenRouter models (seedream/flux/riverflow) reject
            # ["image", "text"] with "No endpoints found that support the
            # requested output modalities". ["image"] works universally.
            response = await client.chat.send_async(
                model=self.openrouter_model,
                modalities=["image"],
                messages=[{"role": "user", "content": content}],  # pyright: ignore[reportArgumentType]
            )
        except Exception as e:
            raise ToolException(f"OpenRouter request failed: {e}")

        image_bytes = await _extract_openrouter_image_bytes(response)
        if image_bytes is None:
            raise ToolException("No image found in OpenRouter response")
        return image_bytes

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
            input_images: list[bytes] | None = None
            if images:
                input_images = await self._download_images(images)

            if self.has_native_key():
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

    async def _upload_and_return(
        self, image_bytes: bytes, context: Any, tool_name: str
    ) -> tuple[str, list[ChatMessageAttachment]]:
        """Upload image to S3 and return text + attachment tuple."""
        job_id = str(XID())
        kind = filetype.guess(image_bytes)
        ext = kind.extension if kind else "png"
        content_type = kind.mime if kind else "image/png"
        image_key = f"{context.agent_id}/image/{tool_name}/{job_id}.{ext}"
        stored_path = await store_image_bytes(
            image_bytes, image_key, content_type=content_type
        )
        if not stored_path:
            raise ToolException("Failed to store image: S3 storage not configured")
        url = get_cdn_url(stored_path)

        attachment: ChatMessageAttachment = {
            "type": ChatMessageAttachmentType.IMAGE,
            "lead_text": None,
            "url": url,
            "json": None,
        }
        return (
            f"Image generated successfully: {url} . "
            "The image has been displayed to the user via attachment. "
            "Do not include the image URL in your response unless the user explicitly asks for it."
        ), [attachment]


def _to_data_url(image: bytes) -> str:
    """Encode raw image bytes as a base64 data URL with the detected MIME."""
    kind = filetype.guess(image)
    mime = kind.mime if kind else "image/png"
    return f"data:{mime};base64,{base64.b64encode(image).decode()}"


def _image_references(images: list[bytes] | None) -> list[dict[str, Any]]:
    """Build image_url content parts from raw input images."""
    return [
        {"type": "image_url", "image_url": {"url": _to_data_url(img)}}
        for img in images or []
    ]


async def _extract_openrouter_image_bytes(response: Any) -> bytes | None:
    """Return the first generated image from an OpenRouter chat-completion.

    Different models emit the image either on ``message.images`` or as an
    ``image_url`` entry in ``message.content``. Data URLs are decoded in-
    process; plain URLs are fetched.
    """
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError):
        return None

    for url in _iter_openrouter_image_urls(message):
        if url.startswith("data:"):
            return base64.b64decode(url.split(",", 1)[1])
        async with httpx.AsyncClient(timeout=30) as client:
            img_resp = await client.get(url, follow_redirects=True)
            img_resp.raise_for_status()
            return img_resp.content
    return None


def _iter_openrouter_image_urls(message: Any):
    """Yield candidate image URLs from an OpenRouter assistant message."""
    for image in getattr(message, "images", None) or []:
        url = getattr(getattr(image, "image_url", None), "url", None)
        if url:
            yield url

    content = getattr(message, "content", None)
    if not isinstance(content, list):
        return
    for part in content:
        part_type = getattr(part, "type", None) or (
            part.get("type") if isinstance(part, dict) else None
        )
        if part_type != "image_url":
            continue
        image_url = getattr(part, "image_url", None) or (
            part.get("image_url") if isinstance(part, dict) else None
        )
        url = getattr(image_url, "url", None) or (
            image_url.get("url") if isinstance(image_url, dict) else None
        )
        if url:
            yield url
