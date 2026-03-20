"""MiniMax image generation skills."""

import base64
import logging
from decimal import Decimal
from typing import override

import httpx
from langchain_core.tools.base import ToolException

from intentkit.config.config import config
from intentkit.skills.image.base import ImageBaseTool

logger = logging.getLogger(__name__)

_MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class MiniMaxImageBase(ImageBaseTool):
    """Base class for MiniMax image generation skills."""

    @override
    def _has_native_key(self) -> bool:
        return bool(config.minimax_api_key)

    @override
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        headers = {
            "Authorization": f"Bearer {config.minimax_api_key}",
        }

        body: dict[str, object] = {
            "model": self.native_model,
            "prompt": prompt,
            "response_format": "base64",
        }

        if images:
            # Use subject reference for image editing
            refs = []
            for img in images:
                b64 = base64.b64encode(img).decode()
                refs.append(
                    {
                        "type": "character",
                        "image_file": f"data:image/png;base64,{b64}",
                    }
                )
            body["subject_reference"] = refs

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{_MINIMAX_BASE_URL}/image_generation",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                base_resp = data.get("base_resp", {})
                if base_resp.get("status_code", 0) != 0:
                    raise ToolException(
                        f"MiniMax image generation failed: {base_resp.get('status_msg', 'Unknown error')}"
                    )

                # Extract base64 image from response
                image_data = data.get("data", {})
                image_base64 = image_data.get("image_base64")
                if not image_base64:
                    raise ToolException("No image data in MiniMax response")

                return base64.b64decode(image_base64)
        except ToolException:
            raise
        except httpx.HTTPStatusError as e:
            raise ToolException(
                f"MiniMax API request failed: {e.response.status_code} {e.response.text[:200]}"
            )
        except Exception as e:
            raise ToolException(f"MiniMax image API error: {e}")


class MiniMaxImage(MiniMaxImageBase):
    """Generate images using MiniMax image-01."""

    name: str = "image_minimax"
    description: str = (
        "Generate images from text prompts using MiniMax image-01. "
        "Supports subject reference for character consistency."
    )
    price: Decimal = Decimal("30")
    native_model: str = "image-01"
