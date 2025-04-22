import logging
from typing import Literal, Optional, Type

import httpx
from epyxid import XID
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.venice_image.base import VeniceImageBaseTool, base_url
from skills.venice_image.input import STYLE_PRESETS, VeniceImageGenerationInput
from utils.s3 import store_image_bytes

logger = logging.getLogger(__name__)


class ImageGenerationFluxDev(VeniceImageBaseTool):
    """Tool for generating versatile images using Venice AI's Flux Dev model.

    This tool takes a text prompt and uses Venice AI's API to generate
    an image based on the description using the versatile Flux Dev model.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "venice_image_generation_flux_dev"
    description: str = (
        "Generate versatile images using Venice AI's Flux Dev model.\n"
        "Provide a text prompt describing the image you want to generate.\n"
        f"Optionally specify a style preset from the following list: {', '.join(STYLE_PRESETS)}.\n"
        "Flux Dev is a powerful model capable of generating high-quality images in various styles.\n"
        "If you have height and width, remember to specify them (up to 2048x2048).\n"
    )
    args_schema: Type[BaseModel] = VeniceImageGenerationInput

    async def _arun(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = 1024,
        height: Optional[int] = 1024,
        style_preset: Optional[str] = "Photographic",
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Implementation of the tool to generate images using Venice AI's Flux Dev model.

        Args:
            prompt: Text prompt describing the image to generate.
            negative_prompt: Negative prompt describing what to avoid. Uses config default if None.
            width: Width of the generated image.
            height: Height of the generated image.
            style_preset: Artistic style preset.
            config: Configuration for the runnable.

        Returns:
            str: URL of the generated image stored in S3.

        Raises:
            Exception: If the image generation fails or API key is missing.
        """
        context = self.context_from_config(config)
        skill_config = context.config

        # Get API key, rate limits, and defaults from config
        api_key = self.get_api_key(context)
        if not api_key:
            raise ValueError("Venice AI API key not found")

        rate_limit_number = skill_config.get("rate_limit_number")
        rate_limit_minutes = skill_config.get("rate_limit_minutes")
        safe_mode = skill_config.get("safe_mode", True)
        hide_watermark = skill_config.get("hide_watermark", True)
        default_negative_prompt = skill_config.get("negative_prompt", "(worst quality: 1.4), bad quality, nsfw")

        # Apply rate limiting if configured for agent-specific key
        if "api_key" in skill_config and rate_limit_number and rate_limit_minutes:
            await self.user_rate_limit_by_category(
                context.user_id, rate_limit_number, rate_limit_minutes
            )
        elif "api_key" not in skill_config: # Apply default system rate limit if using system key
             await self.user_rate_limit_by_category(context.user_id, 10, 1440) # Example: 10 requests per day

        # Use provided negative prompt or the default from config
        final_negative_prompt = negative_prompt if negative_prompt is not None else default_negative_prompt

        # Prepare the request payload
        payload = {
            "model": "flux-dev",
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": 30,
            "safe_mode": safe_mode,
            "hide_watermark": hide_watermark,
            "cfg_scale": 7.0,
            "style_preset": style_preset,
            "negative_prompt": final_negative_prompt,
            "return_binary": True,
        }
        logger.debug(f"Venice API payload: {payload}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        api_url = f"{base_url}/api/v1/image/generate"

        try:
            # Make the API request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    api_url, json=payload, headers=headers, timeout=180 # Increased timeout
                )
                logger.debug(f"Venice API status code: {response.status_code}")
                # Check content type - binary means success
                content_type = str(response.headers.get('content-type', '')).lower()
                if content_type.startswith('image/'):
                    # Store the image bytes
                    stored_url = await store_image_bytes(response.content)
                    return stored_url
                else:
                    # If not an image, assume error and try to parse JSON
                    try:
                        error_data = response.json()
                        logger.error(f"Venice API error response: {error_data}")
                        raise Exception(f"Venice API error: {error_data.get('message', response.text)}")
                    except Exception as json_err:
                        logger.error(f"Failed to parse Venice API error response: {json_err}")
                        response.raise_for_status() # Raise original HTTP error if JSON parsing fails

        except httpx.HTTPStatusError as e:
            logger.error(f"Venice API HTTP error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"Venice API error: {e.response.status_code} - {e.response.text}") from e
        except httpx.RequestError as e:
            logger.error(f"Venice API request error: {e}")
            raise Exception(f"Venice API request error: {str(e)}") from e
        except Exception as e:
            logger.error(f"Error generating image with Venice AI: {e}", exc_info=True)
            raise Exception(f"Error generating image with Venice AI: {str(e)}") from e