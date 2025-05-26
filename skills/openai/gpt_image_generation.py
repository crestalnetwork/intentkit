"""GPT image generation skill for OpenAI."""

import base64
import logging
from typing import Literal, Type

import openai
from epyxid import XID
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.openai.base import OpenAIBaseTool
from utils.s3 import store_image_bytes

logger = logging.getLogger(__name__)


class GPTImageGenerationInput(BaseModel):
    """Input for GPTImageGeneration tool."""

    prompt: str = Field(
        description="Text prompt describing the image to generate.",
    )
    size: Literal["1024x1024", "1536x1024", "1024x1536", "auto"] = Field(
        default="auto",
        description="Size of the generated image. Options: 1024x1024, 1536x1024, 1024x1536, auto",
    )
    quality: Literal["high", "medium", "low", "auto"] = Field(
        default="auto",
        description="Quality of the generated image. Options: high, medium, low, auto",
    )
    background: Literal["transparent", "opaque", "auto"] = Field(
        default="auto",
        description="Background transparency. Options: transparent, opaque, auto",
    )


class GPTImageGeneration(OpenAIBaseTool):
    """Tool for generating high-quality images using OpenAI's GPT-Image-1 model.

    This tool takes a text prompt and uses OpenAI's API to generate
    an image based on the description using the GPT-Image-1 model.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "gpt_image_generation"
    description: str = (
        "Generate images using OpenAI's GPT-Image-1 model.\n"
        "Provide a text prompt describing the image you want to generate.\n"
        "GPT-Image-1 is a powerful image generation model capable of creating detailed, "
        "high-quality images from text descriptions.\n"
        "You can specify size, quality, and background parameters for more control.\n"
    )
    args_schema: Type[BaseModel] = GPTImageGenerationInput

    async def _arun(
        self,
        prompt: str,
        size: Literal["1024x1024", "1536x1024", "1024x1536", "auto"] = "auto",
        quality: Literal["high", "medium", "low", "auto"] = "auto",
        background: Literal["transparent", "opaque", "auto"] = "auto",
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Implementation of the tool to generate images using OpenAI's GPT-Image-1 model.

        Args:
            prompt: Text prompt describing the image to generate.
            size: Size of the generated image. Options: 1024x1024, 1536x1024, 1024x1536, auto
            quality: Quality of the generated image. Options: high, medium, low, auto
            background: Background transparency. Options: transparent, opaque, auto
            config: Configuration for the runnable.

        Returns:
            str: URL of the generated image.

        Raises:
            Exception: If the image generation fails.
        """
        context = self.context_from_config(config)

        # Get the OpenAI API key from the skill store
        api_key = self.get_api_key(context)

        # Generate a unique job ID
        job_id = str(XID())

        try:
            # Initialize the OpenAI client
            client = openai.OpenAI(api_key=api_key)

            # Determine content type based on background setting
            content_type = "image/png" if background == "transparent" else "image/jpeg"

            # Make the API request to generate the image
            response = client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size=size,
                quality=quality,
                background=background,
                moderation="low",  # Using low moderation as specified
                n=1,
            )

            # GPT-Image-1 always returns base64-encoded images
            # Get the base64 image data from the response
            base64_image = response.data[0].b64_json

            # Log the usage information if available
            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                logger.info(
                    f"GPT-Image-1 generation usage: "
                    f"input_tokens={usage.input_tokens}, "
                    f"output_tokens={usage.output_tokens}, "
                    f"total_tokens={usage.total_tokens}"
                )

                # Log detailed input tokens information if available
                if (
                    hasattr(usage, "input_tokens_details")
                    and usage.input_tokens_details
                ):
                    details = usage.input_tokens_details
                    logger.info(f"Input tokens details: {details}")

            # Decode the base64 string to bytes
            image_bytes = base64.b64decode(base64_image)

            # Generate a key with agent ID as prefix
            image_key = f"{context.agent.id}/gpt-image/{job_id}"

            # Store the image bytes and get the CDN URL
            stored_url = await store_image_bytes(image_bytes, image_key, content_type)

            # Return the stored image URL
            return stored_url

        except openai.OpenAIError as e:
            error_message = f"OpenAI API error: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

        except Exception as e:
            error_message = f"Error generating image with GPT-Image-1: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)
