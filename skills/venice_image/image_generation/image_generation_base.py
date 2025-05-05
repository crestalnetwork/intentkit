import base64
import hashlib
import logging
from typing import Any, Dict, Literal, Optional, Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

# Import the generic base
from skills.venice_image.base import VeniceImageBaseTool, base_url
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
        """
        Core implementation to generate images using a specified Venice AI model.
        Handles API call to /image/generate and response processing.
        Expects a JSON response with base64 encoded image data.
        Returns the API response JSON (excluding the base64 image data)
        augmented with S3 storage URL and image hash.
        """
        context = self.context_from_config(config)
        skill_config = context.config

        api_key = self.get_api_key(context)
        if not api_key:
            logger.error(f"Venice AI API key not found for skill '{self.name}'")
            raise ValueError(
                "Venice AI API key not found. Please configure it in system or agent settings for the 'venice_image' category."
            )

        await self.apply_rate_limit(context)

        safe_mode = skill_config.get("safe_mode", False)
        hide_watermark = skill_config.get("hide_watermark", True)
        embed_exif_metadata = skill_config.get("embed_exif_metadata", False)
        default_negative_prompt = skill_config.get(
            "negative_prompt", "(worst quality: 1.4), bad quality, nsfw"
        )

        final_negative_prompt = (
            negative_prompt if negative_prompt is not None else default_negative_prompt
        )

        default_steps = 30

        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "width": width,
            "seed": seed,
            "height": height,
            "format": format,
            "steps": default_steps,
            "safe_mode": safe_mode,
            "embed_exif_metadata": embed_exif_metadata,
            "hide_watermark": hide_watermark,
            "cfg_scale": cfg_scale if cfg_scale else 7.0,
            "style_preset": style_preset,
            "negative_prompt": final_negative_prompt,
            "return_binary": False,
        }

        payload = {k: v for k, v in payload.items() if v is not None}

        logger.debug(f"Venice Image API ({self.model_id}) payload: {payload}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        api_url = f"{base_url}/api/v1/image/generate"

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(api_url, json=payload, headers=headers)
                logger.debug(
                    f"Venice Image API ({self.model_id}) status code: {response.status_code}, Headers: {response.headers}"
                )

                content_type = str(response.headers.get("content-type", "")).lower()

                if response.status_code == 200 and content_type.startswith(
                    "application/json"
                ):
                    try:
                        json_response: Dict[str, Any] = response.json()
                        logger.debug(
                            f"Venice Image API ({self.model_id}) JSON response received (pre-strip): {json_response}"
                        )

                        images_list = json_response.get("images")
                        if (
                            not images_list
                            or not isinstance(images_list, list)
                            or len(images_list) == 0
                        ):
                            logger.error(
                                f"Venice Image API ({self.model_id}) returned success status but no 'images' found in the JSON response: {json_response}"
                            )
                            raise ValueError(
                                f"Venice Image API ({self.model_id}) returned success status but no images found in the response."
                            )

                        base64_image_string = images_list[0]

                        try:
                            image_bytes = base64.b64decode(base64_image_string)
                        except (TypeError, base64.binascii.Error) as decode_error:
                            logger.error(
                                f"Failed to decode base64 image string from Venice API ({self.model_id}): {decode_error}. String (start): {base64_image_string[:100]}..."
                            )
                            raise ValueError(
                                f"Received invalid base64 image data from Venice Image API ({self.model_id})."
                            ) from decode_error

                        response_format = (
                            json_response.get("request", {})
                            .get("data", {})
                            .get("format")
                        )
                        file_extension = response_format if response_format else format
                        content_type_for_s3 = f"image/{file_extension}"

                        image_hash = hashlib.sha256(image_bytes).hexdigest()
                        key = f"{self.category}/{self.model_id}/{image_hash}.{file_extension}"

                        stored_url = await store_image_bytes(
                            image_bytes, key, content_type=content_type_for_s3
                        )
                        logger.info(
                            f"Venice ({self.model_id}) image generated and stored: {stored_url}"
                        )

                        # Add the storage URL and hash to the response dictionary
                        json_response["image_url"] = stored_url
                        json_response["image_bytes_sha256"] = image_hash

                        # *** Remove the original base64 image data before returning ***
                        removed_images = json_response.pop("images", None)
                        if removed_images:
                            logger.debug(
                                f"Removed 'images' key containing base64 data from the final response dict for model {self.model_id}."
                            )
                        else:
                            logger.warning(
                                f"Expected 'images' key not found in JSON response for model {self.model_id} when trying to remove it."
                            )

                        # Return the modified JSON response (without base64 images)
                        return json_response

                    except Exception as json_proc_err:
                        logger.error(
                            f"Error processing successful JSON response from Venice Image API ({self.model_id}): {json_proc_err}",
                            exc_info=True,
                        )
                        raise Exception(
                            f"Failed to process the successful response from Venice Image API ({self.model_id})."
                        ) from json_proc_err

                else:
                    error_message = f"Venice Image API ({self.model_id}) error:"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get(
                            "message", error_data.get("detail", response.text)
                        )
                        error_message += (
                            f" Status {response.status_code} - {error_detail}"
                        )
                        logger.error(f"{error_message} | Response: {error_data}")
                    except Exception:
                        error_message += (
                            f" Status {response.status_code} - {response.text}"
                        )
                        logger.error(f"{error_message}")

                    if response.status_code == 400:
                        raise ValueError(
                            f"Bad request to Venice Image API ({self.model_id}). Check parameters. API response: {response.text}"
                        )
                    elif response.status_code == 401:
                        raise PermissionError(
                            f"Authentication failed for Venice Image API ({self.model_id}). Check API key."
                        )
                    elif response.status_code == 429:
                        raise ConnectionAbortedError(
                            f"Rate limit exceeded for Venice Image API ({self.model_id}). Try again later."
                        )
                    else:
                        response.raise_for_status()

        except httpx.HTTPStatusError as e:
            raise Exception(
                f"Venice Image API error ({self.model_id}): Status {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Venice Image API ({self.model_id}) request timed out: {e}")
            raise TimeoutError(
                f"The request to Venice AI ({self.model_id}) timed out after 180 seconds."
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Venice Image API ({self.model_id}) request error: {e}")
            raise ConnectionError(
                f"Could not connect to Venice Image API ({self.model_id}): {str(e)}"
            ) from e
        except (ValueError, PermissionError, ConnectionAbortedError, TimeoutError) as e:
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while generating image with Venice AI ({self.model_id}): {e}",
                exc_info=True,
            )
            raise Exception(
                f"An unexpected error occurred while generating the image using model {self.model_id}."
            ) from e
