import base64
import hashlib
import logging
from typing import Any, Dict, Literal, Optional, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

# Import the generic base
from skills.base import ToolException
from skills.venice_image.base import VeniceImageBaseTool
from skills.venice_image.image_generation.image_generation_input import (
    VeniceImageGenerationInput,
)
from utils.s3 import store_image_bytes

logger = logging.getLogger(__name__)


class VeniceImageGenerationBaseTool(VeniceImageBaseTool):
    """
    Base class for Venice AI *Image Generation* tools.
    Inherits from VeniceAIBaseTool and handles specifics of the
    /image/generate endpoint.
    """

    # --- Attributes specific to Image Generation ---
    args_schema: Type[BaseModel] = VeniceImageGenerationInput

    # --- Attributes Subclasses MUST Define ---
    name: str = Field(description="The unique name of the image generation tool/model.")
    description: str = Field(
        description="A description of what the image generation tool/model does."
    )
    model_id: str = Field(
        description="The specific model ID used in the Venice Image API call."
    )

    async def _arun(
        self,
        prompt: str,
        seed: Optional[int] = None,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = 1024,
        height: Optional[int] = 1024,
        format: Literal["png", "jpeg", "webp"] = "png",
        cfg_scale: Optional[float] = 7.5,
        style_preset: Optional[str] = "Photographic",
        config: RunnableConfig = None,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            context = self.context_from_config(config)
            await self.apply_venice_rate_limit(context)

            final_negative_prompt = negative_prompt or self.negative_prompt

            payload = {
                "model": self.model_id,
                "prompt": prompt,
                "width": width,
                "height": height,
                "seed": seed,
                "format": format,
                "steps": 30,
                "safe_mode": self.safe_mode,
                "hide_watermark": self.hide_watermark,
                "embed_exif_metadata": self.embed_exif_metadata,
                "cfg_scale": cfg_scale or 7.0,
                "style_preset": style_preset,
                "negative_prompt": final_negative_prompt,
                "return_binary": False,
            }

            # Strip out None values
            payload = {k: v for k, v in payload.items() if v is not None}

            result, error = await self.post("/api/v1/image/generate", payload, context)

            if error:
                raise ToolException(f"Venice Image Generation API error: {error}")

            base64_image_string = result.get("images", [None])[0]
            if not base64_image_string:
                raise ToolException("No image data found in Venice Image API response.")

            try:
                image_bytes = base64.b64decode(base64_image_string)
            except Exception as decode_error:
                raise ToolException("Invalid base64 image data.") from decode_error

            response_format = (
                result.get("request", {}).get("data", {}).get("format", format)
            )
            file_extension = response_format or format
            content_type = f"image/{file_extension}"

            image_hash = hashlib.sha256(image_bytes).hexdigest()
            key = f"{self.category}/{self.model_id}/{image_hash}.{file_extension}"

            stored_url = await store_image_bytes(
                image_bytes, key, content_type=content_type
            )

            # Cleanup & enrich the response
            result.pop("images", None)
            result["image_url"] = stored_url
            result["image_bytes_sha256"] = image_hash

            return result
        except ToolException as e:
            raise e
        except Exception as e:
            raise ToolException(
                "An unexpected error occurred during the image generation process."
            ) from e
