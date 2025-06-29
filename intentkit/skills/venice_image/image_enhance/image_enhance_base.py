from typing import Type

from pydantic import BaseModel, Field

# Import the generic base and shared input
from intentkit.skills.venice_image.base import VeniceImageBaseTool
from intentkit.skills.venice_image.image_enhance.image_enhance_input import (
    VeniceImageEnhanceInput,
)


class VeniceImageEnhanceBaseTool(VeniceImageBaseTool):
    """
    Base class for Venice AI *Image Enchanching* tools.
    Inherits from VeniceAIBaseTool and handles specifics of the
    /image/upscale endpoint
    """

    args_schema: Type[BaseModel] = VeniceImageEnhanceInput
    name: str = Field(description="The unique name of the image Enchanching tool.")
    description: str = Field(
        description="A description of what the image Enchanching tool does."
    )
