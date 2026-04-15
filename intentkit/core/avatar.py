import base64
import io
import logging
from typing import Any

import httpx
import openrouter
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from PIL import Image

from intentkit.clients.s3 import store_image_bytes
from intentkit.config.config import config

logger = logging.getLogger(__name__)

OPENROUTER_IMAGE_MODEL = "bytedance-seed/seedream-4.5"

# Prompt fields to extract from agent objects for avatar generation.
# These are (field_name, display_label) pairs.
_PROMPT_FIELDS: list[tuple[str, str]] = [
    ("name", "Name"),
    ("description", "Description"),
    ("purpose", "Purpose"),
    ("personality", "Personality"),
    ("principles", "Principles"),
    ("prompt", "System Prompt"),
    ("prompt_append", "Additional Prompt"),
    ("extra_prompt", "Extra Prompt"),
]

_AVATAR_SYSTEM_PROMPT = """\
You are an expert avatar designer for AI agents. Based on the agent profile below, \
write a concise visual description for a profile picture (avatar).

Requirements for the avatar:
- Modern, clean, and visually striking design suitable as a profile picture
- A single central subject or icon that captures the agent's essence
- Professional and memorable, works well at small sizes (like a chat avatar)
- Abstract or stylized — do NOT include any text, letters, or words in the image
- Use colors and shapes that reflect the agent's personality and purpose
- Square composition with the subject centered

Output ONLY the image generation prompt, nothing else."""


_USER_AVATAR_SYSTEM_PROMPT = """\
You are an expert avatar designer. Based on the user-provided description below, \
write a concise visual description for a profile picture (avatar).

Requirements for the avatar:
- Modern, clean, and visually striking design suitable as a profile picture
- A single central subject or icon
- Works well at small sizes (like a chat avatar)
- Abstract or stylized — do NOT include any text, letters, or words in the image
- Square composition with the subject centered

Output ONLY the image generation prompt, nothing else."""


def _normalize_avatar(image_bytes: bytes, size: int = 512) -> bytes:
    """Crop image to square (center crop) and resize to size x size, return PNG bytes."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _download_image(url: str) -> bytes:
    """Download image from URL and return raw bytes."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.content


async def generate_image_openrouter(prompt: str) -> bytes | None:
    """Generate image using OpenRouter (bytedance-seed/seedream-4.5).

    OpenRouter does not expose an OpenAI-compatible `/images/generations`
    endpoint; image generation routes through chat completions with the
    `modalities` parameter. Image-only models reject `["image", "text"]`,
    so we ask for `["image"]` which is accepted by all image-output models.
    """
    try:
        client = openrouter.OpenRouter(
            api_key=config.openrouter_api_key,
            http_referer="https://github.com/crestalnetwork/intentkit",
            x_open_router_title="IntentKit",
            x_open_router_categories="cloud-agent",
            timeout_ms=120_000,
        )
        response = await client.chat.send_async(
            model=OPENROUTER_IMAGE_MODEL,
            modalities=["image"],
            messages=[{"role": "user", "content": prompt}],
        )
        url = _extract_openrouter_image_url(response)
        if not url:
            logger.error("OpenRouter image generation returned no image url")
            return None
        if url.startswith("data:"):
            return base64.b64decode(url.split(",", 1)[1])
        return await _download_image(url)
    except Exception as e:
        logger.error("OpenRouter image generation failed: %s", e)
    return None


def _extract_openrouter_image_url(response: Any) -> str | None:
    """Pull the first image URL from an OpenRouter chat-completions response.

    Different image models put the result in different places: most use
    ``message.images[0].image_url.url``, a few return it as an ``image_url``
    content part. Check both so avatar and skill callers stay consistent.
    """
    try:
        message = response.choices[0].message
    except (AttributeError, IndexError):
        return None

    images = getattr(message, "images", None) or []
    if images:
        url = getattr(getattr(images[0], "image_url", None), "url", None)
        if url:
            return url

    content = getattr(message, "content", None)
    if isinstance(content, list):
        for part in content:
            part_type = getattr(part, "type", None) or (
                part.get("type") if isinstance(part, dict) else None
            )
            if part_type != "image_url":
                continue
            image_url = getattr(part, "image_url", None) or (
                part.get("image_url") if isinstance(part, dict) else None
            )
            url = getattr(image_url, "url", None) or (
                image_url.get("url") if isinstance(image_url, dict) else None
            )
            if url:
                return url
    return None


async def generate_image_google(prompt: str) -> bytes | None:
    """Generate image using Google Gemini gemini-3.1-flash-image-preview."""
    try:
        client = genai.Client(api_key=config.google_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-3.1-flash-image-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        if response.candidates:
            content = response.candidates[0].content
            if content and content.parts:
                for part in content.parts:
                    if (
                        part.inline_data
                        and part.inline_data.mime_type
                        and part.inline_data.mime_type.startswith("image/")
                    ):
                        return part.inline_data.data
    except Exception as e:
        logger.error("Google image generation failed: %s", e)
    return None


async def generate_image_openai(prompt: str) -> bytes | None:
    """Generate image using OpenAI gpt-image-1-mini."""
    try:
        client = AsyncOpenAI(api_key=config.openai_api_key)
        # gpt-image-1 minimum size is 1024x1024, no 512x512 support
        response = await client.images.generate(
            model="gpt-image-1-mini",
            prompt=prompt,
            size="1024x1024",
            quality="low",
            n=1,
        )
        if response.data and response.data[0].b64_json:
            return base64.b64decode(response.data[0].b64_json)
        if response.data and response.data[0].url:
            return await _download_image(response.data[0].url)
    except Exception as e:
        logger.error("OpenAI image generation failed: %s", e)
    return None


async def generate_image_xai(prompt: str) -> bytes | None:
    """Generate image using xAI grok-imagine-image."""
    try:
        client = AsyncOpenAI(
            api_key=config.xai_api_key,
            base_url="https://api.x.ai/v1",
        )
        response = await client.images.generate(
            model="grok-imagine-image",
            prompt=prompt,
            n=1,
            response_format="b64_json",
        )
        if response.data and response.data[0].b64_json:
            return base64.b64decode(response.data[0].b64_json)
        if response.data and response.data[0].url:
            return await _download_image(response.data[0].url)
    except Exception as e:
        logger.error("xAI image generation failed: %s", e)
    return None


async def select_model_and_generate(prompt: str) -> bytes | None:
    """Select image generation provider based on available API keys and generate image.

    Priority: OpenRouter > Google > OpenAI > xAI

    Returns raw image bytes on success, None on failure.
    """
    providers: list[tuple[str | None, str, Any]] = [
        (
            config.openrouter_api_key,
            "OpenRouter/seedream-4.5",
            generate_image_openrouter,
        ),
        (config.google_api_key, "Google/gemini-3.1-flash-image", generate_image_google),
        (config.openai_api_key, "OpenAI/gpt-image-1-mini", generate_image_openai),
        (config.xai_api_key, "xAI/grok-imagine-image", generate_image_xai),
    ]

    for api_key, provider_name, generate_fn in providers:
        if not api_key:
            continue
        logger.info("Generating avatar using %s", provider_name)
        image_bytes = await generate_fn(prompt)
        if image_bytes:
            return image_bytes
        logger.warning("%s returned no image, trying next provider", provider_name)

    logger.error("All image generation providers failed or none configured")
    return None


def build_agent_profile(agent_id: str, agent: Any) -> str:
    """Extract prompt-related fields from an agent object and build a profile string."""
    sections: list[str] = []
    for field_name, label in _PROMPT_FIELDS:
        value = getattr(agent, field_name, None)
        if value and isinstance(value, str) and value.strip():
            sections.append(f"### {label}\n{value.strip()}")

    if not sections:
        # Fallback: at least use the agent id
        return f"An AI agent with ID: {agent_id}"

    return "\n\n".join(sections)


async def generate_image_prompt_from_profile(profile: str, system_prompt: str) -> str:
    """Use a cheap LLM to turn a profile description into an image generation prompt.

    Args:
        profile: Text describing the subject (agent profile, team name, etc.)
        system_prompt: System prompt guiding the LLM to produce an image prompt.

    Returns:
        The generated image prompt string.

    Raises:
        Exception: If the LLM call fails.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from intentkit.models.llm import create_llm_model
    from intentkit.models.llm_picker import pick_summarize_model

    model_name = pick_summarize_model()
    llm = await create_llm_model(model_name, temperature=0.9)
    model = await llm.create_instance()

    response = await model.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=profile),
        ]
    )
    image_prompt = response.content
    if not isinstance(image_prompt, str):
        image_prompt = str(image_prompt)

    return image_prompt


async def _generate_image_prompt(agent_id: str, agent: Any) -> str:
    """Use a cheap LLM to turn agent profile into an image generation prompt."""
    profile = build_agent_profile(agent_id, agent)

    try:
        image_prompt = await generate_image_prompt_from_profile(
            f"Agent Profile:\n{profile}", _AVATAR_SYSTEM_PROMPT
        )
        logger.info(
            "Generated avatar prompt for agent %s: %s", agent_id, image_prompt[:200]
        )
        return image_prompt

    except Exception as e:
        logger.error("Failed to generate avatar prompt via LLM: %s", e)
        name = getattr(agent, "name", None) or agent_id
        return (
            f"A modern, minimalist, professional AI avatar for an agent called '{name}'. "
            f"Abstract geometric design, vibrant gradient colors, clean lines, centered composition, no text."
        )


async def _render_and_store(image_prompt: str, s3_key: str) -> str | None:
    """Generate image bytes from a prompt, normalize, and upload to S3.

    Shared by `generate_avatar` and `generate_avatar_from_description`.
    """
    image_bytes = await select_model_and_generate(image_prompt)
    if not image_bytes:
        return None

    try:
        image_bytes = _normalize_avatar(image_bytes)
    except Exception as e:
        logger.error("Failed to normalize avatar image: %s", e)
        return None

    try:
        relative_path = await store_image_bytes(
            image_bytes, s3_key, content_type="image/png"
        )
        if not relative_path:
            logger.error("store_image_bytes returned empty path")
            return None
        return relative_path
    except Exception as e:
        logger.error("Failed to upload avatar to S3: %s", e)
        return None


async def generate_avatar(agent_id: str, agent: Any) -> str | None:
    """Generate an avatar image for an agent and upload it to S3.

    Args:
        agent_id: The agent's unique identifier (used for the S3 storage path).
        agent: An agent-like object with prompt fields (Agent, AgentCreate, AgentUpdate, etc.).

    Returns:
        The image path without CDN prefix (e.g. "local/intentkit/avatars/{id}/xxx.png"),
        or None if generation failed.
    """
    from epyxid import XID

    image_prompt = await _generate_image_prompt(agent_id, agent)
    return await _render_and_store(image_prompt, f"avatars/{agent_id}/{XID()}.png")


async def generate_avatar_from_description(
    description: str, s3_prefix: str
) -> str | None:
    """Generate an avatar from a free-text user description and upload to S3.

    Args:
        description: Free-text user description of the desired avatar.
        s3_prefix: S3 key prefix where the result is stored
            (e.g. "avatars/generated/{team_id}"). The final key is
            "{s3_prefix}/{XID}.png".

    Returns:
        Relative S3 path on success, None on failure.
    """
    from epyxid import XID

    try:
        image_prompt = await generate_image_prompt_from_profile(
            description, _USER_AVATAR_SYSTEM_PROMPT
        )
    except Exception as e:
        logger.error("Failed to generate avatar prompt via LLM: %s", e)
        # Fallback: use the raw description as the image prompt
        image_prompt = (
            f"A modern, minimalist profile avatar. {description}. "
            "Abstract geometric design, vibrant colors, clean lines, centered "
            "composition, no text."
        )

    return await _render_and_store(image_prompt, f"{s3_prefix.rstrip('/')}/{XID()}.png")
