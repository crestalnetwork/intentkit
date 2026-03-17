import io
import logging
from decimal import Decimal

import aiohttp
import openai
from langchain_core.tools import ArgsSchema
from langchain_core.tools.base import ToolException
from PIL import Image
from pydantic import BaseModel, Field

from intentkit.skills.openai.base import OpenAIBaseTool

logger = logging.getLogger(__name__)


class ImageToTextInput(BaseModel):
    """Input for ImageToText tool."""

    image: str = Field(description="URL of the image to analyze.")


class ImageToTextOutput(BaseModel):
    """Output for ImageToText tool."""

    description: str = Field(description="Text description of the image.")
    width: int = Field(description="Image width.")
    height: int = Field(description="Image height.")


class ImageToText(OpenAIBaseTool):
    """Tool for converting images to text descriptions using OpenAI's GPT-4o model."""

    name: str = "image_to_text"
    description: str = "Describe an image in detail given its URL. Returns a text description with dimensions."
    price: Decimal = Decimal("200")
    args_schema: ArgsSchema | None = ImageToTextInput

    async def _arun(self, image: str, **kwargs) -> ImageToTextOutput:
        """Implementation of the tool to convert images to text.

        Args:
            image (str): URL of the image to convert to text.

        Returns:
            ImageToTextOutput: Object containing the text description and image dimensions.
        """
        context = self.get_context()
        logger.debug("context: %s", context)

        # Get the OpenAI client from configuration or agent settings
        api_key = self.get_api_key()
        client = openai.AsyncOpenAI(api_key=api_key)

        try:
            # Download the image from the URL
            async with aiohttp.ClientSession() as session:
                async with session.get(image) as response:
                    if response.status != 200:
                        raise ToolException(
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
            logger.error("Error converting image to text: %s", e)
            raise ToolException(f"Error converting image to text: {str(e)}")
