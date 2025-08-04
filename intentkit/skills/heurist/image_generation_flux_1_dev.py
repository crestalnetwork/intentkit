import logging
from typing import Optional, Type

import httpx
from epyxid import XID
from pydantic import BaseModel, Field

from intentkit.skills.heurist.base import HeuristBaseTool
from intentkit.utils.s3 import store_image

logger = logging.getLogger(__name__)


class ImageGenerationFlux1DevInput(BaseModel):
    """Input for ImageGenerationFlux1Dev tool."""

    prompt: str = Field(
        description="Text prompt describing the image to generate.",
    )
    neg_prompt: Optional[str] = Field(
        default="",
        description="Negative prompt describing what to avoid in the generated image.",
    )
    width: Optional[int] = Field(
        default=1024,
        le=2048,
        description="Width of the generated image.",
    )
    height: Optional[int] = Field(
        default=1024,
        le=2048,
        description="Height of the generated image.",
    )


class ImageGenerationFlux1Dev(HeuristBaseTool):
    """Tool for generating versatile images using Heurist AI's Flux.1-dev model.

    This tool takes a text prompt and uses Heurist's API to generate
    an image based on the description using the versatile Flux.1-dev model.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "heurist_image_generation_flux_1_dev"
    description: str = (
        "Generate images using Heurist AI's Flux.1-dev model.\n"
        "Provide a text prompt describing the image you want to generate.\n"
        "Flux.1-dev is a versatile, general-purpose model capable of generating images in any style.\n"
        "If you have height and width, remember to specify them.\n"
    )
    args_schema: Type[BaseModel] = ImageGenerationFlux1DevInput

    async def _arun(
        self,
        prompt: str,
        neg_prompt: Optional[str] = "",
        width: Optional[int] = 1024,
        height: Optional[int] = 680,
        **kwargs,
    ) -> str:
        """Implementation of the tool to generate images using Heurist AI's Flux.1-dev model.

        Args:
            prompt: Text prompt describing the image to generate.
            neg_prompt: Negative prompt describing what to avoid in the generated image.
            width: Width of the generated image.
            height: Height of the generated image.
            config: Configuration for the runnable.

        Returns:
            str: URL of the generated image.
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        skill_config = skill_config

        # Get the Heurist API key from the skill store
        if "api_key" in skill_config and skill_config["api_key"]:
            api_key = skill_config["api_key"]
            if skill_config.get("rate_limit_number") and skill_config.get(
                "rate_limit_minutes"
            ):
                await self.user_rate_limit_by_category(
                    context.user_id,
                    skill_config["rate_limit_number"],
                    skill_config["rate_limit_minutes"],
                )
        else:
            api_key = self.skill_store.get_system_config("heurist_api_key")
            await self.user_rate_limit_by_category(context.user_id, 10, 1440)

        # Generate a unique job ID
        job_id = str(XID())

        # Prepare the request payload
        payload = {
            "job_id": job_id,
            "model_input": {
                "SD": {
                    "prompt": prompt,
                    "neg_prompt": neg_prompt,
                    "num_iterations": 22,
                    "width": width,
                    "height": height,
                    "guidance_scale": 3,
                    "seed": -1,
                }
            },
            "model_id": "Flux.1-dev",
            "deadline": 180,
            "priority": 1,
        }
        logger.debug(f"Heurist API payload: {payload}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Make the API request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://sequencer.heurist.xyz/submit_job",
                    json=payload,
                    headers=headers,
                    timeout=120,
                )
                logger.debug(f"Heurist API response: {response.text}")
                response.raise_for_status()

            # Store the image URL
            image_url = response.text.strip('"')
            # Generate a key with agent ID as prefix
            image_key = f"{context.agent_id}/heurist/{job_id}"
            # Store the image and get the CDN URL
            stored_url = await store_image(image_url, image_key)

            # Return the stored image URL
            return stored_url

        except httpx.HTTPStatusError as e:
            # Extract error details from response
            try:
                error_json = e.response.json()
                error_code = error_json.get("error", "")
                error_message = error_json.get("message", "")
                full_error = f"Heurist API error: Error code: {error_code}, Message: {error_message}"
            except Exception:
                full_error = f"Heurist API error: {e}"

            logger.error(full_error)
            raise Exception(full_error)

        except Exception as e:
            logger.error(f"Error generating image with Heurist: {e}")
            raise Exception(f"Error generating image with Heurist: {str(e)}")
