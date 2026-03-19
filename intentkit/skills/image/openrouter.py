"""OpenRouter-only image generation skills."""

import logging
from decimal import Decimal
from typing import override

from intentkit.skills.image.base import ImageBaseTool

logger = logging.getLogger(__name__)


class OpenRouterImageBase(ImageBaseTool):
    """Base class for OpenRouter-only image generation skills."""

    @override
    def _has_native_key(self) -> bool:
        return False

    @override
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        # Should never be called since _has_native_key returns False
        raise NotImplementedError


class FluxPro(OpenRouterImageBase):
    """Generate images using FLUX.2 Pro via OpenRouter."""

    name: str = "image_flux_pro"
    description: str = "Generate images from text prompts using FLUX.2 Pro."
    price: Decimal = Decimal("30")
    openrouter_model: str = "black-forest-labs/flux.2-pro"


class Riverflow(OpenRouterImageBase):
    """Generate images using Riverflow v2 via OpenRouter."""

    name: str = "image_riverflow"
    description: str = "Generate images from text prompts using Riverflow v2 Fast."
    price: Decimal = Decimal("20")
    openrouter_model: str = "sourceful/riverflow-v2-fast"
