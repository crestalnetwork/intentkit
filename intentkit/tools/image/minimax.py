"""MiniMax image generation tools."""

import base64
import binascii
import logging
from decimal import Decimal
from typing import override

import httpx
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, ConfigDict, Field

from intentkit.config.config import config
from intentkit.tools.image.base import ImageBaseTool

logger = logging.getLogger(__name__)

_MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class MiniMaxImageBase(ImageBaseTool):
    """Base class for MiniMax image generation tools."""

    @override
    def has_native_key(self) -> bool:
        return bool(config.minimax_plan_api_key)

    @override
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        headers = {
            "Authorization": f"Bearer {config.minimax_plan_api_key}",
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
    title: str = "MiniMax image-01"
    description: str = (
        "Generate images from text prompts using MiniMax image-01. "
        "Supports subject reference for character consistency."
    )
    price: Decimal = Decimal("30")
    native_model: str = "image-01"


class MiniMaxH3Input(BaseModel):
    """Arguments for H3 text-to-image generation."""

    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(description="Text description of the image to generate")


class MiniMaxH3Image(MiniMaxImageBase):
    """Generate one image through the regional MiniMax H3 generations API."""

    name: str = "image_minimax_h3"
    title: str = "MiniMax H3 Image"
    description: str = "Generate an image from a text prompt using MiniMax H3 Image."
    native_model: str = "MiniMax-H3-Image"
    args_schema: ArgsSchema | None = MiniMaxH3Input
    price: Decimal = Decimal("30")

    @override
    async def _generate_native(self, prompt: str, images: list[bytes] | None) -> bytes:
        if images:
            raise ToolException(
                "MiniMax H3 image generation only accepts text prompts."
            )
        base_url = {"global": _MINIMAX_BASE_URL, "cn": "https://api.minimax.cn/v1"}.get(
            config.minimax_image_region
        )
        if not base_url:
            raise ToolException("MINIMAX_IMAGE_REGION must be global or cn.")

        # A generation can take ten minutes. Retrying after a disconnect can bill twice.
        async with httpx.AsyncClient(timeout=610) as client:
            response = await client.post(
                f"{base_url}/images/generations",
                headers={"Authorization": f"Bearer {config.minimax_plan_api_key}"},
                json={
                    "model": self.native_model,
                    "prompt": prompt,
                    "response_format": "b64_json",
                },
            )
        response.raise_for_status()
        payload = response.json()
        entries = payload.get("data") if isinstance(payload, dict) else None
        if (
            not isinstance(entries, list)
            or not entries
            or not isinstance(entries[0], dict)
        ):
            raise ToolException("MiniMax H3 response contained no image.")
        item = entries[
            0
        ]  # n defaults to one, matching ImageBaseTool's single attachment.
        error = item.get("error")
        if isinstance(error, dict):
            raise ToolException(
                f"MiniMax H3 image generation failed: {error.get('message', 'Unknown error')}"
            )
        encoded = item.get("b64_json")
        if not isinstance(encoded, str) or not encoded:
            raise ToolException("MiniMax H3 response contained no image.")
        try:
            return base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ToolException(
                "MiniMax H3 response contained invalid base64 image data."
            ) from exc


class MiniMaxH3ImageHighspeed(MiniMaxH3Image):
    """Highspeed variant of the MiniMax H3 text-to-image tool."""

    name: str = "image_minimax_h3_highspeed"
    title: str = "MiniMax H3 Image Highspeed"
    description: str = (
        "Generate an image from a text prompt using MiniMax H3 Image Highspeed."
    )
    native_model: str = "MiniMax-H3-Image-Highspeed"
