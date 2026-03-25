"""Grok image generation skills."""

import logging
from decimal import Decimal
from typing import override

import httpx
import openai
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.image.base import ImageBaseTool

logger = logging.getLogger(__name__)


class GrokImageBase(ImageBaseTool):
    """Base class for Grok image generation skills."""

    @override
    def has_native_key(self) -> bool:
        return bool(config.xai_api_key)

    @override
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        if images:
            raise ToolException("Grok image skills do not support image editing")

        try:
            client = openai.OpenAI(
                api_key=config.xai_api_key,
                base_url="https://api.x.ai/v1",
            )

            response = client.images.generate(
                model=self.native_model,
                prompt=prompt,
                n=1,
            )

            # Grok returns URL, need to download
            if not response.data:
                raise ToolException("Empty response from xAI image API")
            image_data = response.data[0]
            if image_data.url:
                async with httpx.AsyncClient(timeout=30) as http_client:
                    resp = await http_client.get(image_data.url, follow_redirects=True)
                    resp.raise_for_status()
                    return resp.content

            raise ToolException("No image URL in Grok response")
        except openai.OpenAIError as e:
            raise ToolException(f"xAI API error: {e}")


class GrokImagePro(GrokImageBase):
    """Generate images using Grok Imagine Image Pro."""

    name: str = "image_grok_pro"
    description: str = "Generate images from text prompts using Grok Imagine Image Pro."
    price: Decimal = Decimal("70")
    native_model: str = "grok-imagine-image-pro"
    openrouter_model: str = "x-ai/grok-imagine-image-pro"


class GrokImage(GrokImageBase):
    """Generate images using Grok Imagine Image."""

    name: str = "image_grok"
    description: str = (
        "Generate images from text prompts using Grok Imagine Image (faster, cheaper)."
    )
    price: Decimal = Decimal("20")
    native_model: str = "grok-imagine-image"
    openrouter_model: str = "x-ai/grok-imagine-image"
