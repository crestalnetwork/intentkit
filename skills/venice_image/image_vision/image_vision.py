import logging
from typing import Any, Type

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, HttpUrl

from skills.base import ToolException
from skills.venice_image.image_vision.image_vision_base import (
    VeniceImageVisionBaseTool,
)
from skills.venice_image.image_vision.image_vision_input import VeniceImageVision
from skills.venice_image.utils import fetch_image_as_base64

logger = logging.getLogger(__name__)


class ImageVision(VeniceImageVisionBaseTool):
    """
    Describes an image provided via URL using the Venice AI API.
    Ideal for understanding the content of an existing image.
    """

    name: str = "image_vision"
    description: str = (
        "Describes an image from a URL using Venice AI.\n"
        "Provide the public URL of the image to describe.\n"
        "Returns a descriptive text of the image."
    )
    args_schema: Type[BaseModel] = VeniceImageVision
    # No model_id needed for the generic vision endpoint currently

    async def _arun(
        self,
        image_url: HttpUrl,
        config: RunnableConfig = None,
        **kwargs,
    ) -> dict[str, Any]:
        try:
            context = self.context_from_config(config)

            await self.apply_venice_rate_limit(context)

            image_base64 = await fetch_image_as_base64(image_url)
            if not image_base64:
                error_msg = f"Failed to fetch or validate image from URL: {image_url}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "result": None}

            payload = {
                "model": "qwen-2.5-vl",
                "messages": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are an AI model that provides detailed descriptions of images. "
                                    "When given an image, you must respond with a description that is as comprehensive and detailed as possible. "
                                    "Focus on identifying all objects, colors, textures, and any other relevant features present in the image. "
                                    "Provide a thorough and exhaustive account of what is visible in the image."
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Provide an extremely detailed description of the image, focusing on every discernible aspect. "
                                    "Include information about objects, colors, textures, lighting conditions, artistic style (if applicable), "
                                    "composition, and any other relevant details that would allow someone to accurately understand and potentially "
                                    "recreate the image. Be as thorough and comprehensive as possible."
                                ),
                            },
                            {"type": "image_url", "image_url": {"url": str(image_url)}},
                        ],
                    },
                ],
            }

            result, error = await self.post("api/v1/chat/completions", payload, context)
            if error:
                raise ToolException(f"Venice Image Vision API error: {error}")
            return result
        except ToolException as e:
            return {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }
        except Exception as e:
            logger.error(f"Error in {self.name}: {str(e)}")
            return {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
            }
