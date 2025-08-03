"""DALL-E image generation skill for OpenAI."""

import logging
from typing import Type

import openai
from epyxid import XID
from pydantic import BaseModel, Field

from intentkit.skills.openai.base import OpenAIBaseTool
from intentkit.utils.s3 import store_image

logger = logging.getLogger(__name__)


class DALLEImageGenerationInput(BaseModel):
    """Input for DALLEImageGeneration tool."""

    prompt: str = Field(
        description="Text prompt describing the image to generate.",
    )
    size: str = Field(
        default="1024x1024",
        description="Size of the generated image. Options: 1024x1024, 1024x1792, 1792x1024",
    )
    quality: str = Field(
        default="hd",
        description="Quality of the generated image. Options: standard, hd",
    )
    style: str = Field(
        default="vivid",
        description="Style of the generated image. Options: vivid, natural",
    )


class DALLEImageGeneration(OpenAIBaseTool):
    """Tool for generating high-quality images using OpenAI's DALL-E 3 model.

    This tool takes a text prompt and uses OpenAI's API to generate
    an image based on the description using the DALL-E 3 model.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "dalle_image_generation"
    description: str = (
        "Generate images using OpenAI's DALL-E 3 model.\n"
        "Provide a text prompt describing the image you want to generate.\n"
        "DALL-E 3 is a powerful image generation model capable of creating detailed, "
        "high-quality images from text descriptions.\n"
        "You can specify size, quality, and style parameters for more control.\n"
    )
    args_schema: Type[BaseModel] = DALLEImageGenerationInput

    async def _arun(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "hd",
        style: str = "vivid",
        **kwargs,
    ) -> str:
        """Implementation of the tool to generate images using OpenAI's DALL-E 3 model.

        Args:
            prompt: Text prompt describing the image to generate.
            size: Size of the generated image. Options: 1024x1024, 1024x1792, 1792x1024
            quality: Quality of the generated image. Options: standard, hd
            style: Style of the generated image. Options: vivid, natural


        Returns:
            str: URL of the generated image.

        Raises:
            Exception: If the image generation fails.
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)

        # Get the OpenAI API key from the skill store
        api_key = skill_config.get("api_key") or self.skill_store.get_system_config(
            "openai_api_key"
        )

        # Generate a unique job ID
        job_id = str(XID())

        try:
            # Initialize the OpenAI client
            client = openai.OpenAI(api_key=api_key)

            # Make the API request to generate the image
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                style=style,
                n=1,
            )

            # Get the image URL from the response
            image_url = response.data[0].url

            # Strip potential double quotes from the response
            image_url = image_url.strip('"')

            # Generate a key with agent ID as prefix
            image_key = f"{context.agent_id}/dalle/{job_id}"

            # Store the image and get the CDN URL
            stored_url = await store_image(image_url, image_key)

            # Return the stored image URL
            return stored_url

        except openai.OpenAIError as e:
            error_message = f"OpenAI API error: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

        except Exception as e:
            error_message = f"Error generating image with DALL-E: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)
