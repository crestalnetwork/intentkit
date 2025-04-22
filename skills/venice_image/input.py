from typing import Optional
from pydantic import BaseModel, Field

STYLE_PRESETS = [
    "3D Model", "Analog Film", "Anime", "Cinematic", "Comic Book",
    "Craft Clay", "Digital Art", "Enhance", "Fantasy Art", "Isometric Style",
    "Line Art", "Lowpoly", "Neon Punk", "Origami", "Photographic",
    "Pixel Art", "Texture", "Advertising", "Food Photography", "Real Estate",
    "Abstract", "Cubist", "Graffiti", "Hyperrealism", "Impressionist",
    "Pointillism", "Pop Art", "Psychedelic", "Renaissance", "Steampunk",
    "Surrealist", "Typography", "Watercolor", "Fighting Game", "GTA",
    "Super Mario", "Minecraft", "Pokemon", "Retro Arcade", "Retro Game",
    "RPG Fantasy Game", "Strategy Game", "Street Fighter", "Legend of Zelda",
    "Architectural", "Disco", "Dreamscape", "Dystopian", "Fairy Tale",
    "Gothic", "Grunge", "Horror", "Minimalist", "Monochrome", "Nautical",
    "Space", "Stained Glass", "Techwear Fashion", "Tribal", "Zentangle",
    "Collage", "Flat Papercut", "Kirigami", "Paper Mache", "Paper Quilling",
    "Papercut Collage", "Papercut Shadow Box", "Stacked Papercut",
    "Thick Layered Papercut", "Alien", "Film Noir", "HDR", "Long Exposure",
    "Neon Noir", "Silhouette", "Tilt-Shift"
]

STYLE_PRESETS_DESCRIPTION = (
    "Optional style preset to apply. Available options: " +
    ", ".join([f"'{s}'" for s in STYLE_PRESETS]) +
    ". Defaults to 'Photographic'."
)


class VeniceImageGenerationInput(BaseModel):
    """Input for General Image Generation Input tool."""

    prompt: str = Field(
        description="Text prompt describing the image to generate.",
    )
    negative_prompt: Optional[str] = Field(
        None,
        description="Negative prompt describing what to avoid in the generated image. If not provided, the default from the agent config will be used.",
    )
    width: Optional[int] = Field(
        default=1024,
        le=2048,
        description="Width of the generated image (up to 2048).",
    )
    height: Optional[int] = Field(
        default=1024,
        le=2048,
        description="Height of the generated image (up to 2048).",
    )
    style_preset: Optional[str] = Field(
        default="Photographic",
        description=STYLE_PRESETS_DESCRIPTION
    )