import logging
from typing import Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from skills.cookiefun.base import CookieFunBaseTool

logger = logging.getLogger(__name__)


class GenerateImageInput(BaseModel):
    """Input for GenerateImage tool."""

    prompt: str = Field(description="Description of the image you want to generate")


class GenerateImage(CookieFunBaseTool):
    """Tool for generating images using Cookie.fun's AI."""

    name: str = "cookiefun_generate_image"
    description: str = (
        "Generate an image using Cookie.fun's AI image generation system.\n"
        "Use this when you need to create an AI-generated image based on a text description."
    )
    args_schema: Type[BaseModel] = GenerateImageInput

    async def _arun(self, prompt: str, config: RunnableConfig = None, **kwargs) -> str:
        """Generate image using Cookie.fun API."""
        context = self.context_from_config(config)
        api_key = context.config.get("api_key")
        if not api_key:
            return "Error: Cookie.fun API key not configured"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.cookie-api.com/api/ai/generate-image",
                    json={"prompt": prompt},
                    headers={"Authorization": api_key},
                    timeout=120.0,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("success"):
                    return data.get("url", "No image URL received")
                else:
                    return f"Error: {data.get('error', 'Unknown error')}"

        except httpx.HTTPError as e:
            logger.error(f"HTTP error when generating image: {str(e)}")
            return f"Error generating image: {str(e)}"
        except Exception as e:
            logger.error(f"Error in image generation: {str(e)}")
            return f"Unexpected error: {str(e)}"
