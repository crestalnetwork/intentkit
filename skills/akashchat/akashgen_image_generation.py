"""AkashGen image generation skill for AkashChat."""

import asyncio
import json
import logging
from typing import Optional, Type

import httpx
from epyxid import XID
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, field_validator

from skills.akashchat.base import AkashChatBaseTool

logger = logging.getLogger(__name__)


class AkashGenImageGenerationInput(BaseModel):
    """Input for AkashGenImageGeneration tool."""

    prompt: str = Field(description="Text prompt describing the image to generate.")
    negative: str = Field(
        default="",
        description="Negative prompt to exclude undesirable elements from the image.",
    )
    sampler: str = Field(
        default="dpmpp_2m",
        description="Sampling method to use for image generation. Default: dpmpp_2m.",
    )
    scheduler: str = Field(
        default="sgm_uniform",
        description="Scheduler to use for image generation. Default: sgm_uniform.",
    )
    preferred_gpu: list[str] = Field(
        default_factory=lambda: ["RTX4090", "A10", "A100", "V100-32Gi", "H100"],
        description="List of preferred GPU types for image generation.",
    )

    @field_validator("preferred_gpu")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                raise ValueError("preferred_gpu must be a list or a JSON array string")
        return v


class AkashGenImageGeneration(AkashChatBaseTool):
    """Tool for generating high-quality images using AkashGen model.

    This tool takes a text prompt and uses AkashChat's API to generate
    an image based on the description using the AkashGen model.

    Attributes:
        name: The name of the tool.
        description: A description of what the tool does.
        args_schema: The schema for the tool's input arguments.
    """

    name: str = "akashgen_image_generation"
    description: str = (
        "Generate images using AkashGen model.\n"
        "Provide a text prompt describing the image you want to generate.\n"
        "AkashGen is a powerful image generation model capable of creating detailed, "
        "high-quality images from text descriptions.\n"
        "You can specify size, quality, and style parameters for more control.\n"
    )
    args_schema: Type[BaseModel] = AkashGenImageGenerationInput

    async def _arun(
        self,
        prompt: str,
        negative: Optional[str] = "",
        sampler: Optional[str] = "dpmpp_2m",
        scheduler: Optional[str] = "sgm_uniform",
        preferred_gpu: Optional[list[str]] = [
            "RTX4090",
            "A10",
            "A100",
            "V100-32Gi",
            "H100",
        ],
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Implementation of the tool to generate images using AkashChat's AkashGen model.

        Args:
            prompt: Text prompt describing the image to generate.
            negative: Negative prompt to exclude undesirable elements from the image.
            sampler: Sampling method to use for image generation. Default: dpmpp_2m.
            scheduler: Scheduler to use for image generation. Default: sgm_uniform.
            preferred_gpu: List of preferred GPU types for image generation.
            config: Configuration for the runnable.

        Returns:
            str: URL of the generated image.

        Raises:
            Exception: If the image generation fails.
        """
        context = self.context_from_config(config)

        # Get the AkashChat API key from the skill store
        api_key = context.config.get("api_key")

        # Generate a unique job ID
        job_id = str(XID())

        try:
            # Prepare the payload for AkashGen API
            payload = {
                "prompt": prompt,
                "negative": negative,
                "sampler": sampler,
                "scheduler": scheduler,
                "preferred_gpu": preferred_gpu,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            # Send the image generation request
            async with httpx.AsyncClient(timeout=60) as client:
                gen_response = await client.post(
                    "https://gen.akash.network/api/generate",
                    json=payload,
                    headers=headers,
                )
                gen_response.raise_for_status()
                gen_data = gen_response.json()
                job_id = gen_data.get("job_id")
                if not job_id:
                    raise Exception(f"No job_id returned from AkashGen: {gen_data}")

                # Poll for status every 3 seconds
                status_url = f"https://gen.akash.network/api/status?ids={job_id}"
                for _ in range(40):  # ~2 minutes max
                    status_response = await client.get(status_url, headers=headers)
                    status_response.raise_for_status()
                    status_data = status_response.json()
                    status_entry = status_data.get(job_id) or (
                        status_data["statuses"][0]
                        if "statuses" in status_data and status_data["statuses"]
                        else None
                    )
                    if not status_entry:
                        raise Exception(f"Malformed status response: {status_data}")
                    if status_entry["status"] == "completed":
                        result = status_entry.get("result")
                        if not result:
                            raise Exception(
                                f"No result found in completed status: {status_entry}"
                            )
                        return result
                    elif status_entry["status"] == "failed":
                        raise Exception(f"Image generation failed: {status_entry}")
                    await asyncio.sleep(3)
                raise Exception(f"Image generation timed out for job_id {job_id}")
        except httpx.HTTPError as e:
            error_message = f"HTTP error during AkashGen image generation: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)
        except Exception as e:
            error_message = f"Error generating image with AkashGen: {str(e)}"
            logger.error(error_message)
            raise Exception(error_message)
