"""Gemini image generation skills."""

import logging
from decimal import Decimal
from io import BytesIO
from typing import Any, override

from langchain_core.tools.base import ToolException
from PIL import Image

from intentkit.config.config import config
from intentkit.skills.image.base import ImageBaseTool

logger = logging.getLogger(__name__)


class GeminiImageBase(ImageBaseTool):
    """Base class for Gemini image generation skills."""

    @override
    def has_native_key(self) -> bool:
        return bool(config.google_api_key)

    @override
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=config.google_api_key)

            # Build contents: text prompt + optional input images
            contents: list[Any] = [prompt]
            if images:
                for img_bytes in images:
                    contents.append(Image.open(BytesIO(img_bytes)))

            response = client.models.generate_content(
                model=self.native_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]
                ),
            )

            # Extract image from response parts
            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if (
                                part.inline_data is not None
                                and part.inline_data.data is not None
                            ):
                                return part.inline_data.data

            raise ToolException("No image found in Gemini response")
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"Gemini API error: {e}")


class GeminiImagePro(GeminiImageBase):
    """Generate images using Gemini 3 Pro."""

    name: str = "image_gemini_pro"
    description: str = "Generate images from text prompts using Gemini 3 Pro."
    price: Decimal = Decimal("130")
    native_model: str = "gemini-3-pro-image-preview"
    openrouter_model: str = "google/gemini-3-pro-image-preview"


class GeminiImageFlash(GeminiImageBase):
    """Generate images using Gemini 3.1 Flash."""

    name: str = "image_gemini_flash"
    description: str = (
        "Generate images from text prompts using Gemini 3.1 Flash (faster, cheaper)."
    )
    price: Decimal = Decimal("70")
    native_model: str = "gemini-3.1-flash-image-preview"
    openrouter_model: str = "google/gemini-3.1-flash-image-preview"
