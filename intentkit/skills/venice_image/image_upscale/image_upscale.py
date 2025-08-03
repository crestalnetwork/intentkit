import logging
from typing import Literal, Optional

from pydantic import HttpUrl

from intentkit.skills.base import ToolException
from intentkit.skills.venice_image.image_upscale.image_upscale_base import (
    VeniceImageUpscaleBaseTool,
)
from intentkit.skills.venice_image.utils import fetch_image_as_base64

logger = logging.getLogger(__name__)


class ImageUpscale(VeniceImageUpscaleBaseTool):
    """
    Upscales an existing image provided via URL by a factor of 2 or 4 using the Venice AI API.
    Ideal for enhancing the resolution of previously generated or existing images.
    """

    # --- Tool Specific Configuration ---
    name: str = "venice_image_upscale"
    description: str = (
        "Upscales an existing image from a URL using Venice AI.\n"
        "Provide the public URL of the image to upscale.\n"
        "Specify the desired scale factor: 2 (for 2x upscale) or 4 (for 4x upscale).\n"
        "Returns the URL of the upscaled image."
    )

    # No model_id needed for the generic upscale endpoint currently
    async def _arun(
        self,
        image_url: HttpUrl,
        scale: Literal[2, 4],
        replication: Optional[float] = 0.35,
        **kwargs,
    ) -> dict:
        """
        Asynchronously upscales an image from the provided URL using the Venice AI API.

        Args:
            image_url (HttpUrl): The public URL of the image to upscale.
            scale (Literal[2, 4]): The scale factor for upscaling (2x or 4x).
            replication (Optional[float]): The replication factor for the upscale process, defaults to 0.35.
            config (RunnableConfig, optional): Configuration for the runnable, if any.
            **kwargs: Additional keyword arguments.

        Returns:
            dict: The API response containing the URL of the upscaled image.

        Raises:
            ToolException: If the image cannot be fetched, validated, or upscaled, or if an API error occurs.
        """

        try:
            context = self.get_context()

            await self.apply_venice_rate_limit(context)

            image_base64 = await fetch_image_as_base64(image_url)
            if not image_base64:
                error_msg = f"Failed to fetch or validate image from URL: {image_url}"
                logger.error(error_msg)
                raise ToolException(
                    str({"success": False, "error": error_msg, "result": None})
                )

            payload = {
                "image": image_base64,
                "scale": scale,
                "replication": replication,
            }
            result, error = await self.post("api/v1/image/upscale", payload, context)
            if error:
                raise ToolException(f"Venice Image Upscale API error: {error}")
            return result
        except ToolException as e:
            raise e
        except Exception as e:
            logger.error(f"Error in {self.name}: {str(e)}")
            raise ToolException(
                str(
                    {
                        "success": False,
                        "error": f"An unexpected error occurred: {str(e)}",
                    }
                )
            )
