# venice_image/base.py
import hashlib
import logging
from typing import Optional, Type

import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from abstracts.skill import SkillStoreABC
from skills.base import IntentKitSkill, SkillContext
from skills.venice_image.input import (
    VeniceImageGenerationInput,
)  # Import the shared input schema

# Ensure this import path is correct for your project structure
# Might be from ..utils.s3 or similar depending on your layout
from utils.s3 import store_image_bytes

logger = logging.getLogger(__name__)

base_url = "https://api.venice.ai"


class VeniceImageBaseTool(IntentKitSkill):
    """Base class for Venice Image generation tools."""

    # --- Attributes Subclasses MUST Define ---
    name: str = Field(description="The unique name of the tool/model.")
    description: str = Field(description="A description of what the tool/model does.")
    model_id: str = Field(
        description="The specific model ID used in the Venice API call."
    )
    # --- Shared Attributes ---
    args_schema: Type[BaseModel] = (
        VeniceImageGenerationInput  # Use the shared input schema
    )
    skill_store: SkillStoreABC = Field(
        description="The skill store for persisting data"
    )

    def get_api_key(self, context: SkillContext) -> Optional[str]:
        """Get the API key, prioritizing agent config then system config."""
        # Check agent config first
        agent_api_key = context.config.get("api_key")
        if agent_api_key:
            logger.debug(f"Using agent-specific Venice API key for skill {self.name}")
            return agent_api_key

        # Fallback to system config
        system_api_key = self.skill_store.get_system_config("venice_api_key")
        if system_api_key:
            logger.debug(f"Using system Venice API key for skill {self.name}")
            return system_api_key

        logger.warning(
            f"No Venice API key found in agent or system config for skill {self.name}"
        )
        return None

    @property
    def category(self) -> str:
        return "venice_image"

    async def _arun(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: Optional[int] = 1024,
        height: Optional[int] = 1024,
        style_preset: Optional[str] = "Photographic",
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """
        Core implementation to generate images using a specified Venice AI model.
        This method is inherited by subclasses and uses self.model_id.
        """
        context = self.context_from_config(config)
        skill_config = context.config  # Agent-specific config for this skill category

        # --- Configuration and Setup ---
        api_key = self.get_api_key(context)
        if not api_key:
            logger.error(f"Venice AI API key not found for skill '{self.name}'")
            raise ValueError(
                "Venice AI API key not found. Please configure it in system or agent settings."
            )

        rate_limit_number = skill_config.get("rate_limit_number")
        rate_limit_minutes = skill_config.get("rate_limit_minutes")
        # Default safe_mode to False as per schema
        safe_mode = skill_config.get("safe_mode", True)
        hide_watermark = skill_config.get("hide_watermark", True)
        default_negative_prompt = skill_config.get(
            "negative_prompt", "(worst quality: 1.4), bad quality, nsfw"
        )

        # Apply rate limiting
        using_agent_key = "api_key" in skill_config and skill_config["api_key"]
        if using_agent_key and rate_limit_number and rate_limit_minutes:
            logger.debug(
                f"Applying agent rate limit ({rate_limit_number}/{rate_limit_minutes} min) for user {context.user_id} on skill {self.name}"
            )
            await self.user_rate_limit_by_category(
                context.user_id, rate_limit_number, rate_limit_minutes
            )
        elif not using_agent_key:
            # Try to get system rate limits if defined, otherwise use hardcoded defaults
            sys_rate_limit_num = self.skill_store.get_system_config(
                "venice_rate_limit_number", 10
            )  # Example: Default 10
            sys_rate_limit_min = self.skill_store.get_system_config(
                "venice_rate_limit_minutes", 1440
            )  # Example: Default 1 day (1440 min)
            if sys_rate_limit_num and sys_rate_limit_min:
                logger.debug(
                    f"Applying system rate limit ({sys_rate_limit_num}/{sys_rate_limit_min} min) for user {context.user_id} on skill {self.name}"
                )
                await self.user_rate_limit_by_category(
                    context.user_id, sys_rate_limit_num, sys_rate_limit_min
                )
            else:
                # Fallback if system limits aren't configured at all
                logger.warning(
                    f"System rate limits for Venice AI not configured. Applying default 10 requests/day for user {context.user_id} on skill {self.name}"
                )
                await self.user_rate_limit_by_category(context.user_id, 10, 1440)

        # Use provided negative prompt or the default from config
        final_negative_prompt = (
            negative_prompt if negative_prompt is not None else default_negative_prompt
        )

        # --- Prepare API Request ---
        # Default steps vary per model, we use a reasonable default here.
        # Could be made configurable per-model if needed via class attributes.
        default_steps = 30
        # Get model-specific defaults if available (example, not implemented from descriptions)
        # steps = getattr(self, 'default_steps', 30)
        # cfg_scale = getattr(self, 'default_cfg', 7.0)

        payload = {
            "model": self.model_id,  # Use the model_id from the subclass
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": default_steps,  # Use the determined steps
            "safe_mode": safe_mode,
            "hide_watermark": hide_watermark,
            "cfg_scale": 7.0,  # Use the determined cfg_scale
            "style_preset": style_preset,
            "negative_prompt": final_negative_prompt,
            "return_binary": True,
        }
        # Clean payload: remove keys with None values as API might not like them
        payload = {k: v for k, v in payload.items() if v is not None}

        logger.debug(f"Venice API ({self.model_id}) payload: {payload}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "image/*, application/json",  # Accept images or JSON errors
        }
        api_url = f"{base_url}/api/v1/image/generate"

        # --- Execute API Call and Handle Response ---
        try:
            async with httpx.AsyncClient(
                timeout=180.0
            ) as client:  # Set timeout on client
                response = await client.post(api_url, json=payload, headers=headers)
                logger.debug(
                    f"Venice API ({self.model_id}) status code: {response.status_code}, Headers: {response.headers}"
                )

                content_type = str(response.headers.get("content-type", "")).lower()

                # Success: Image received
                if response.status_code == 200 and content_type.startswith("image/"):
                    image_bytes = response.content
                    # Use prompt and model in hash for better uniqueness if needed, but content hash is usually sufficient
                    image_hash = hashlib.sha256(image_bytes).hexdigest()
                    file_extension = content_type.split("/")[-1]  # e.g. png, jpeg
                    # Sanitize extension if needed
                    if "+" in file_extension:
                        file_extension = file_extension.split("+")[0]
                    if not file_extension:
                        file_extension = "png"  # Default extension

                    key = f"venice/{self.model_id}/{image_hash}.{file_extension}"  # e.g., venice/flux-dev/a1b2c3d4e5f6a7b8.png

                    # Store the image bytes
                    stored_url = await store_image_bytes(
                        image_bytes, key, content_type=content_type
                    )
                    logger.info(
                        f"Venice ({self.model_id}) image generated and stored: {stored_url}"
                    )
                    return stored_url

                # Error: Handle non-200 or non-image responses
                else:
                    error_message = f"Venice API ({self.model_id}) error:"
                    try:
                        # Attempt to parse JSON error response
                        error_data = response.json()
                        error_message += f" Status {response.status_code} - {error_data.get('message', response.text)}"
                        logger.error(f"{error_message} | Response: {error_data}")
                    except Exception as json_err:
                        # Fallback if response is not JSON
                        error_message += (
                            f" Status {response.status_code} - {response.text}"
                        )
                        logger.error(
                            f"{error_message} | Failed to parse JSON response: {json_err}"
                        )

                    # Raise a more informative error based on status if possible
                    if response.status_code == 400:
                        raise ValueError(
                            f"Bad request to Venice API ({self.model_id}). Check parameters. API response: {response.text}"
                        )
                    elif response.status_code == 401:
                        raise PermissionError(
                            f"Authentication failed for Venice API ({self.model_id}). Check API key."
                        )
                    elif response.status_code == 429:
                        raise ConnectionAbortedError(
                            f"Rate limit exceeded for Venice API ({self.model_id}). Try again later."
                        )
                    else:
                        response.raise_for_status()  # Raise HTTPStatusError for other non-2xx codes

        except httpx.HTTPStatusError as e:
            # Logged above, re-raise a potentially more user-friendly exception
            raise Exception(
                f"Venice API error ({self.model_id}): Status {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Venice API ({self.model_id}) request timed out: {e}")
            raise TimeoutError(
                f"The request to Venice AI ({self.model_id}) timed out after 180 seconds."
            ) from e
        except httpx.RequestError as e:
            logger.error(f"Venice API ({self.model_id}) request error: {e}")
            raise ConnectionError(
                f"Could not connect to Venice API ({self.model_id}): {str(e)}"
            ) from e
        except Exception as e:
            logger.error(
                f"Error generating image with Venice AI ({self.model_id}): {e}",
                exc_info=True,
            )
            # Avoid leaking internal details unless necessary
            raise Exception(
                f"An unexpected error occurred while generating the image using model {self.model_id}."
            ) from e
