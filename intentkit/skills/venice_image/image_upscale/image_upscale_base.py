from langchain_core.tools import ArgsSchema
from pydantic import Field

# Import the generic base and shared input
from intentkit.skills.venice_image.base import VeniceImageBaseTool
from intentkit.skills.venice_image.image_upscale.image_upscale_input import (
    VeniceImageUpscaleInput,
)


class VeniceImageUpscaleBaseTool(VeniceImageBaseTool):
    """
    Base class for Venice AI *Image Upscaling* tools.
    Inherits from VeniceAIBaseTool and handles specifics of the
    /image/upscale endpoint
    """

    args_schema: ArgsSchema | None = VeniceImageUpscaleInput
    name: str = Field(description="The unique name of the image upscaling tool.")
    description: str = Field(
        description="A description of what the image upscaling tool does."
    )
