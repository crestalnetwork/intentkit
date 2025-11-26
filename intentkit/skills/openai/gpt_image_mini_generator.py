"""GPT image mini generator skill for OpenAI."""

import base64
import logging
from typing import Literal

import openai
from epyxid import XID
from pydantic import BaseModel

from intentkit.clients.s3 import store_image_bytes
from intentkit.skills.openai.base import OpenAIBaseTool
from intentkit.skills.openai.gpt_image_generation import GPTImageGenerationInput

logger = logging.getLogger(__name__)


class GPTImageMiniGenerator(OpenAIBaseTool):
    """Tool for generating images using OpenAI's GPT-Image-1-Mini model."""

    name: str = "gpt_image_mini_generator"
    description: str = (
        "Generate images using OpenAI's GPT-Image-1-Mini model.\n"
        "Provide a text prompt describing the image you want to generate.\n"
        "GPT-Image-1-Mini delivers high-quality images with faster performance at a lower cost.\n"
        "You can specify size, quality, and background parameters for more control.\n"
    )
    args_schema: type[BaseModel] = GPTImageGenerationInput

    async def _arun(
        self,
        prompt: str,
        size: Literal["1024x1024", "1536x1024", "1024x1536", "auto"] = "auto",
        quality: Literal["high", "medium", "low", "auto"] = "auto",
        background: Literal["transparent", "opaque", "auto"] = "auto",
        **kwargs,
    ) -> str:
        """Generate images using OpenAI's GPT-Image-1-Mini model."""
        context = self.get_context()
        api_key = self.get_api_key()
        job_id = str(XID())

        try:
            client = openai.OpenAI(api_key=api_key)

            content_type = "image/png" if background == "transparent" else "image/jpeg"

            response = client.images.generate(
                model="gpt-image-1-mini",
                prompt=prompt,
                size=size,
                quality=quality,
                background=background,
                moderation="low",
                n=1,
            )

            base64_image = response.data[0].b64_json

            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                logger.info(
                    "GPT-Image-1-Mini generation usage: "
                    f"input_tokens={usage.input_tokens}, "
                    f"output_tokens={usage.output_tokens}, "
                    f"total_tokens={usage.total_tokens}"
                )

                if (
                    hasattr(usage, "input_tokens_details")
                    and usage.input_tokens_details
                ):
                    details = usage.input_tokens_details
                    logger.info(f"Input tokens details: {details}")

            image_bytes = base64.b64decode(base64_image)

            image_key = f"{context.agent_id}/gpt-image-mini/{job_id}"

            stored_url = await store_image_bytes(image_bytes, image_key, content_type)

            return stored_url

        except openai.OpenAIError as e:
            error_message = f"OpenAI API error: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

        except Exception as e:
            error_message = f"Error generating image with GPT-Image-1-Mini: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)
