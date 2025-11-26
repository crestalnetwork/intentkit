"""GPT avatar generator skill for OpenAI."""

import base64
import logging

import openai
from epyxid import XID
from pydantic import BaseModel, Field

from intentkit.clients.s3 import store_image_bytes
from intentkit.skills.openai.base import OpenAIBaseTool

logger = logging.getLogger(__name__)

AVATAR_PROMPT_PREFIX = (
    "Create an image suitable for a profile picture, with a clean background but not pure white, "
    "and a clear subject that is recognizable even at small sizes. If there are no style requirements "
    "in the subsequent description, use anime style. The content is as follows:"
)


class GPTAvatarGeneratorInput(BaseModel):
    """Input schema for the GPT avatar generator skill."""

    prompt: str = Field(
        description="Description of the avatar or profile image to generate.",
    )


class GPTAvatarGenerator(OpenAIBaseTool):
    """Tool for generating avatar-friendly images using OpenAI's GPT-Image-1-Mini model."""

    name: str = "gpt_avatar_generator"
    description: str = (
        "Generate avatar-ready profile images using OpenAI's GPT-Image-1-Mini model."
    )
    args_schema: type[BaseModel] = GPTAvatarGeneratorInput

    async def _arun(self, prompt: str, **kwargs) -> str:
        """Generate avatar-friendly images using OpenAI's GPT-Image-1-Mini model."""
        context = self.get_context()
        api_key = self.get_api_key()
        job_id = str(XID())

        composed_prompt = (
            f"{AVATAR_PROMPT_PREFIX}\n{prompt.strip()}"
            if prompt
            else AVATAR_PROMPT_PREFIX
        )

        try:
            client = openai.OpenAI(api_key=api_key)

            response = client.images.generate(
                model="gpt-image-1-mini",
                prompt=composed_prompt,
                size="1024x1024",
                quality="medium",
                background="opaque",
                moderation="low",
                n=1,
            )

            base64_image = response.data[0].b64_json

            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                logger.info(
                    "GPT-Image-1-Mini avatar generation usage: "
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

            image_key = f"{context.agent_id}/gpt-avatar/{job_id}"

            stored_url = await store_image_bytes(
                image_bytes,
                image_key,
                "image/jpeg",
            )

            return stored_url

        except openai.OpenAIError as e:
            error_message = f"OpenAI API error: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)

        except Exception as e:
            error_message = f"Error generating avatar with GPT-Image-1-Mini: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)
