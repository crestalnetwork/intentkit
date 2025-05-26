"""GPT image-to-image generation skill for OpenAI."""

import base64
import logging
from io import BytesIO
from typing import Literal, Type

import httpx
import openai
from epyxid import XID
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.openai.base import OpenAIBaseTool
from utils.s3 import store_image_bytes

logger = logging.getLogger(__name__)


class GPTImageToImageInput(BaseModel):
    """Input for GPTImageToImage tool."""

    image_url: str = Field(
        description="URL of the source image to edit.",
    )
    prompt: str = Field(
        description="Text prompt describing the desired edits to the image.",
    )
    size: Literal["1024x1024", "1536x1024", "1024x1536", "auto"] = Field(
        default="auto",
        description="Size of the generated image. Options: 1024x1024, 1536x1024, 1024x1536, auto",
    )
    quality: Literal["high", "medium", "low", "auto"] = Field(
        default="auto",
        description="Quality of the generated image. Options: high, medium, low, auto",
    )


class GPTImageToImage(OpenAIBaseTool):
    """Tool for editing images using OpenAI's GPT-Image-1 model.

    This tool takes a source image URL and a text prompt, then uses OpenAI's API to
    generate an edited version of the image based on the description.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "gpt_image_to_image"
    description: str = (
        "Edit images using OpenAI's GPT-Image-1 model.\n"
        "Provide a source image URL and a text prompt describing the desired edits.\n"
        "GPT-Image-1 is a powerful image editing model capable of transforming images "
        "based on text descriptions.\n"
        "You can specify size and quality parameters for more control.\n"
    )
    args_schema: Type[BaseModel] = GPTImageToImageInput

    async def _arun(
        self,
        image_url: str,
        prompt: str,
        size: Literal["1024x1024", "1536x1024", "1024x1536", "auto"] = "auto",
        quality: Literal["high", "medium", "low", "auto"] = "auto",
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Implementation of the tool to edit images using OpenAI's GPT-Image-1 model.

        Args:
            image_url: URL of the source image to edit.
            prompt: Text prompt describing the desired edits to the image.
            size: Size of the generated image. Options: 1024x1024, 1536x1024, 1024x1536, auto
            quality: Quality of the generated image. Options: high, medium, low, auto
            config: Configuration for the runnable.

        Returns:
            str: URL of the edited image.

        Raises:
            Exception: If the image editing fails.
        """
        context = self.context_from_config(config)

        # Get the OpenAI API key from the skill store
        api_key = self.get_api_key(context)

        # Generate a unique job ID
        job_id = str(XID())

        try:
            # Download the image from the URL asynchronously
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, follow_redirects=True)
                response.raise_for_status()
                image_data = response.content

            # Initialize the OpenAI client
            client = openai.OpenAI(api_key=api_key)

            # Import required modules for file handling
            import os
            import tempfile

            from PIL import Image

            # Create a temporary file with .png extension
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_path = temp_file.name

                # Open the image, convert to RGB if needed, and save as PNG
                img = Image.open(BytesIO(image_data))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(temp_path, format="PNG")

            # Open the temporary file in binary read mode
            # This provides both .read() method and .name attribute that OpenAI SDK needs
            image_file = open(temp_path, "rb")

            # Make the API request to edit the image
            try:
                response = client.images.edit(
                    model="gpt-image-1",
                    image=image_file,  # Use the file object with .read() method and .name attribute
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=1,
                )

                # GPT-Image-1 always returns base64-encoded images
                # Get the base64 image data from the response
                base64_image = response.data[0].b64_json

                # Log the usage information if available
                if hasattr(response, "usage") and response.usage:
                    usage = response.usage
                    logger.info(
                        f"GPT-Image-1 edit usage: "
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
                image_key = f"{context.agent.id}/gpt-image-edit/{job_id}"

                # Store the image bytes and get the CDN URL
                stored_url = await store_image_bytes(image_bytes, image_key)
            finally:
                # Close and remove the temporary file
                image_file.close()
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

            # Return the stored image URL
            return stored_url

        except httpx.HTTPError as e:
            error_message = f"Failed to download image from URL {image_url}: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

        except openai.OpenAIError as e:
            error_message = f"OpenAI API error: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

        except Exception as e:
            error_message = f"Error editing image with GPT-Image-1: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)
