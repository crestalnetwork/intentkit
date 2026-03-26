from pydantic import Field

# Import the generic base and shared input
from intentkit.skills.venice_image.base import VeniceImageBaseTool


class VeniceImageVisionBaseTool(VeniceImageBaseTool):
    """
    Base class for Venice AI *Image Vision* tools.
    Inherits from VeniceAIBaseTool and handles specifics of the
    /chat/completions endpoint.
    """

    name: str = Field(
        default="", description="The unique name of the image vision tool."
    )
    description: str = Field(
        default="", description="A description of what the image vision tool does."
    )
