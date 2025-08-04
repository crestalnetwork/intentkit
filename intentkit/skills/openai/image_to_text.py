import io
import logging
from typing import Type

import aiohttp
import openai
from PIL import Image
from pydantic import BaseModel, Field

from intentkit.skills.openai.base import OpenAIBaseTool

logger = logging.getLogger(__name__)


class ImageToTextInput(BaseModel):
    """Input for ImageToText tool."""

    image: str = Field(
        description="URL of the image to convert to text.",
    )


class ImageToTextOutput(BaseModel):
    """Output for ImageToText tool."""

    description: str = Field(description="Detailed text description of the image.")
    width: int = Field(description="Width of the processed image.")
    height: int = Field(description="Height of the processed image.")


class ImageToText(OpenAIBaseTool):
    """Tool for converting images to text using OpenAI's GPT-4o model.

    This tool takes an image URL and uses OpenAI's vision capabilities
    to generate a detailed text description of the image content.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "image_to_text"
    description: str = (
        "Convert an image to detailed text description.\n"
        "Provide a URL to the image to analyze and get a comprehensive textual description.\n"
        "Optimized for DALL-E generated images and preserves as many details as possible."
    )
    args_schema: Type[BaseModel] = ImageToTextInput

    async def _arun(self, image: str, **kwargs) -> ImageToTextOutput:
        """Implementation of the tool to convert images to text.

        Args:
            image (str): URL of the image to convert to text.

        Returns:
            ImageToTextOutput: Object containing the text description and image dimensions.
        """
        context = self.get_context()
        skill_config = context.agent.skill_config(self.category)
        logger.debug(f"context: {context}")

        # Get the OpenAI client from the skill store
        api_key = skill_config.get("api_key") or self.skill_store.get_system_config(
            "openai_api_key"
        )
        client = openai.AsyncOpenAI(api_key=api_key)

        try:
            # Download the image from the URL
            async with aiohttp.ClientSession() as session:
                async with session.get(image) as response:
                    if response.status != 200:
                        raise Exception(
                            f"Failed to download image from URL: {response.status}"
                        )

                    # Get image data
                    image_data = await response.read()
                    img = Image.open(io.BytesIO(image_data))

                    # Get original dimensions
                    orig_width, orig_height = img.size

                    # Calculate new dimensions with longest side as 1024 (for reference only)
                    max_size = 1024
                    if orig_width >= orig_height:
                        scaled_width = max_size
                        scaled_height = int(orig_height * (max_size / orig_width))
                    else:
                        scaled_height = max_size
                        scaled_width = int(orig_width * (max_size / orig_height))

            # Use OpenAI API to analyze the image (using original image)
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert image analyzer. Describe the image in great detail, capturing all visual elements, colors, composition, subjects, and context. If there are people in the picture, be sure to clearly describe the person's skin color, hair color, expression, direction, etc. For DALL-E generated images, pay special attention to artistic style, lighting effects, and fantastical elements. Preserve as many details as possible in your description.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this image in detail:"},
                            {
                                "type": "image_url",
                                "image_url": {"url": image, "detail": "high"},
                            },
                        ],
                    },
                ],
                max_tokens=1000,
            )

            # Return the text description and scaled image dimensions
            return ImageToTextOutput(
                description=response.choices[0].message.content,
                width=scaled_width,
                height=scaled_height,
            )

        except Exception as e:
            logger.error(f"Error converting image to text: {e}")
            raise Exception(f"Error converting image to text: {str(e)}")
