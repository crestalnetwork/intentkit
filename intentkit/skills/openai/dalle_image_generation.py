"""DALL-E image generation skill for OpenAI."""

import logging
from decimal import Decimal

import openai
from epyxid import XID
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from pydantic import BaseModel, Field

from intentkit.clients.s3 import get_cdn_url, store_image
from intentkit.skills.openai.base import OpenAIBaseTool

logger = logging.getLogger(__name__)


class DALLEImageGenerationInput(BaseModel):
    """Input for DALLEImageGeneration tool."""

    prompt: str = Field(description="Image description prompt.")
    size: str = Field(
        default="1024x1024",
        description="1024x1024, 1024x1792, or 1792x1024",
    )
    quality: str = Field(default="hd", description="standard or hd")
    style: str = Field(default="vivid", description="vivid or natural")


class DALLEImageGeneration(OpenAIBaseTool):
    """Tool for generating images using OpenAI's DALL-E 3 model."""

    name: str = "dalle_image_generation"
    description: str = "Generate images from text prompts using DALL-E 3."
    price: Decimal = Decimal("200")
    args_schema: ArgsSchema | None = DALLEImageGenerationInput

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

        # Get the OpenAI API key from configuration or agent settings
        api_key = self.get_api_key()

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

            # Store the image and get the relative path
            stored_path = await store_image(image_url, image_key)

            # Return the full CDN URL so the agent can output an accessible link
            return get_cdn_url(stored_path)

        except openai.OpenAIError as e:
            error_message = f"OpenAI API error: {str(e)}"
            raise ToolException(error_message)

        except Exception as e:
            error_message = f"Error generating image with DALL-E: {str(e)}"
            raise ToolException(error_message)
