"""Grok image generation tools."""

import logging
from decimal import Decimal
from typing import override

import httpx
import openai
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.tools.image.base import ImageBaseTool

logger = logging.getLogger(__name__)


class GrokImageBase(ImageBaseTool):
    """Base class for Grok image generation tools."""

    @override
    def has_native_key(self) -> bool:
        return bool(config.xai_api_key)

    @override
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        if images:
            raise ToolException("Grok image tools do not support image editing")

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


class GrokImage(GrokImageBase):
    """Generate images using Grok Imagine Image."""

    name: str = "image_grok"
    title: str = "Grok Imagine"
    description: str = "Generate images from text prompts using Grok Imagine Image."
    price: Decimal = Decimal("20")
    native_model: str = "grok-imagine-image"
    openrouter_model: str = "x-ai/grok-imagine-image"
