import logging
from typing import Optional

from pydantic import HttpUrl

from intentkit.skills.base import ToolException
from intentkit.skills.venice_image.image_enhance.image_enhance_base import (
    VeniceImageEnhanceBaseTool,
)
from intentkit.skills.venice_image.utils import fetch_image_as_base64

logger = logging.getLogger(__name__)


class ImageEnhance(VeniceImageEnhanceBaseTool):
    """
    Enhances an existing image provided via URL using the Venice AI enhancer (not upscaling).
    Useful for improving visual quality, adding style, or refining image features.
    """

    name: str = "venice_image_enhance"
    description: str = (
        "Enhances an existing image from a URL using Venice AI.\n"
        "Provide the public URL of the image to enhance.\n"
        "Specify enhancement creativity level and a required prompt for style.\n"
        "Returns the URL of the enhanced image."
    )

    async def _arun(
        self,
        image_url: HttpUrl,
        enhancePrompt: str,
        replication: Optional[float] = 0.35,
        enhanceCreativity: Optional[float] = 0.5,
        **kwargs,
    ) -> dict:
        """
        Applies AI enhancement to an image without changing its size.
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
                "scale": 1,
                "enhance": True,
                "replication": replication,
                "enhanceCreativity": enhanceCreativity,
                "enhancePrompt": enhancePrompt,
            }

            result, error = await self.post("api/v1/image/upscale", payload, context)
            if error:
                raise ToolException(f"Venice Image Enhance API error: {error}")
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
