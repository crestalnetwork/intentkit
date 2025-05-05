import hashlib
import logging
from typing import Literal, Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, HttpUrl

# Import the generic base and shared input
from skills.venice_image.base import VeniceImageBaseTool, base_url
from skills.venice_image.image_upscale.image_upscale_input import (
    VeniceImageUpscaleInput,
)
from skills.venice_image.utils import fetch_image_as_bytes
from utils.s3 import store_image_bytes  # Assuming this handles S3 storage

logger = logging.getLogger(__name__)
api_url = f"{base_url}/api/v1/image/upscale"


class VeniceImageUpscaleBaseTool(VeniceImageBaseTool):
    """
    Base class for Venice AI *Image Upscaling* tools.
    Inherits from VeniceAIBaseTool and handles specifics of the
    /image/upscale endpoint using multipart/form-data.
    """

    args_schema: Type[BaseModel] = VeniceImageUpscaleInput
    name: str = Field(description="The unique name of the image upscaling tool.")
    description: str = Field(
        description="A description of what the image upscaling tool does."
    )

    async def _arun(
        self,
        image_url: HttpUrl,
        scale: Literal[2, 4],
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        context = self.context_from_config(config)

        api_key = self.get_api_key(context)
        if not api_key:
            logger.error(f"Venice AI API key not found for skill '{self.name}'")
            raise ValueError(
                "Venice AI API key not found. Please configure it in system or agent settings for the 'venice_image' category."
            )

        await self.apply_rate_limit(context)

        logger.info(f"Fetching image from URL for upscaling: {image_url}")
        image_bytes = await fetch_image_as_bytes(image_url)
        if not image_bytes:
            raise ValueError(f"Failed to fetch or validate image from URL: {image_url}")

        try:
            filename = (
                image_url.path.split("/")[-1] if image_url.path else "input_image"
            )
        except Exception:
            filename = "input_image.unknown"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "image/*, application/json",
        }
        form_data = {"scale": str(scale)}
        files_data = {"image": (filename, image_bytes)}

        logger.debug(
            f"Calling Venice Upscale API: {api_url} with scale={scale} for image from {image_url}"
        )

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    api_url,
                    headers=headers,
                    data=form_data,
                    files=files_data,
                )

                content_type = str(response.headers.get("content-type", "")).lower()

                if response.status_code == 200 and content_type.startswith("image/"):
                    upscaled_image_bytes = response.content
                    image_hash = hashlib.sha256(upscaled_image_bytes).hexdigest()
                    file_extension = content_type.split("/")[-1].split("+")[0] or "png"

                    key = f"{self.category}/upscaled/{image_hash}.{file_extension}"

                    stored_url = await store_image_bytes(
                        upscaled_image_bytes, key, content_type=content_type
                    )
                    logger.info(
                        f"Venice image upscaled ({scale}x) and stored: {stored_url}"
                    )
                    return stored_url

                else:
                    error_message = "Venice Upscale API error:"
                    try:
                        error_data = response.json()
                        error_message += f" Status {response.status_code} - {error_data.get('message', response.text)}"
                        logger.error(f"{error_message} | Response: {error_data}")
                    except Exception as json_err:
                        error_message += (
                            f" Status {response.status_code} - {response.text}"
                        )
                        logger.error(
                            f"{error_message} | Failed to parse JSON response: {json_err}"
                        )

                    if response.status_code == 400:
                        raise ValueError(
                            f"Bad request to Venice Upscale API. Check parameters/image format. API response: {response.text}"
                        )
                    elif response.status_code == 401:
                        raise PermissionError(
                            "Authentication failed for Venice Upscale API. Check API key."
                        )
                    elif response.status_code == 413:
                        raise ValueError(
                            f"Input image potentially too large for Venice Upscale API. API response: {response.text}"
                        )
                    elif response.status_code == 429:
                        raise ConnectionAbortedError(
                            "Rate limit exceeded for Venice Upscale API. Try again later."
                        )
                    else:
                        response.raise_for_status()

        except httpx.HTTPStatusError as e:
            raise Exception(
                f"Venice Upscale API error: Status {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Venice Upscale API request timed out: {e}")
            raise TimeoutError(
                "The request to Venice AI Upscale timed out after 180 seconds."
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Venice Upscale API request error: {e}")
            raise ConnectionError(
                f"Could not connect to Venice Upscale API: {str(e)}"
            ) from e
        except Exception as e:
            logger.error(f"Error upscaling image with Venice AI: {e}", exc_info=True)
            raise Exception(
                "An unexpected error occurred while upscaling the image."
            ) from e
