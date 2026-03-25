"""GPT image generation skills."""

import base64
import logging
from decimal import Decimal
from io import BytesIO
from typing import override

import httpx
import openai
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.image.base import ImageBaseTool

logger = logging.getLogger(__name__)


class GPTImageBase(ImageBaseTool):
    """Base class for GPT image generation skills."""

    @override
    def has_native_key(self) -> bool:
        return bool(config.openai_api_key)

    @override
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        try:
            client = openai.OpenAI(api_key=config.openai_api_key)

            if images:
                # Image editing mode
                image_file = BytesIO(images[0])
                image_file.name = "input.png"
                response = client.images.edit(
                    model=self.native_model,
                    image=image_file,
                    prompt=prompt,
                )
            else:
                # Text-to-image mode
                response = client.images.generate(
                    model=self.native_model,
                    prompt=prompt,
                    n=1,
                )

            if not response.data:
                raise ToolException("Empty response from OpenAI image API")
            image_data = response.data[0]
            if image_data.b64_json:
                return base64.b64decode(image_data.b64_json)

            # Some models return URL instead
            if image_data.url:
                async with httpx.AsyncClient(timeout=30) as http_client:
                    resp = await http_client.get(image_data.url, follow_redirects=True)
                    resp.raise_for_status()
                    return resp.content

            raise ToolException("No image data in OpenAI response")
        except openai.OpenAIError as e:
            raise ToolException(f"OpenAI API error: {e}")


class GPTImageFlagship(GPTImageBase):
    """Generate images using GPT Image 1.5."""

    name: str = "image_gpt"
    description: str = "Generate images from text prompts using GPT Image 1.5."
    price: Decimal = Decimal("50")
    native_model: str = "gpt-image-1.5"
    openrouter_model: str = "openai/gpt-image-1.5"


class GPTImageMini(GPTImageBase):
    """Generate images using GPT Image 1 Mini."""

    name: str = "image_gpt_mini"
    description: str = (
        "Generate images from text prompts using GPT Image 1 Mini (faster, cheaper)."
    )
    price: Decimal = Decimal("20")
    native_model: str = "gpt-image-1-mini"
    openrouter_model: str = "openai/gpt-image-1-mini"
