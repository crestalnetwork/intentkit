import base64
import logging
from typing import Any

import httpx
from google import genai
from google.genai import types
from openai import AsyncOpenAI

from intentkit.clients.s3 import store_image_bytes
from intentkit.config.config import config

logger = logging.getLogger(__name__)

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


async def _download_image(url: str) -> bytes:
    """Download image from URL and return raw bytes."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.content


async def _generate_image_openrouter(prompt: str) -> bytes | None:
    """Generate image using OpenRouter with bytedance-seed/seedream-4.5."""
    try:
        client = AsyncOpenAI(
            api_key=config.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        response = await client.images.generate(
            model="bytedance-seed/seedream-4.5",
            prompt=prompt,
            size="1024x1024",
            n=1,
        )
        if response.data and response.data[0].b64_json:
            return base64.b64decode(response.data[0].b64_json)
        if response.data and response.data[0].url:
            return await _download_image(response.data[0].url)
    except Exception as e:
        logger.warning(f"OpenRouter image generation failed: {e}")
    return None


async def _generate_image_google(prompt: str) -> bytes | None:
    """Generate image using Google Gemini gemini-2.5-flash with native image output."""
    try:
        client = genai.Client(api_key=config.google_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
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
        logger.warning(f"Google image generation failed: {e}")
    return None


async def _generate_image_openai(prompt: str) -> bytes | None:
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
        logger.warning(f"OpenAI image generation failed: {e}")
    return None


async def _generate_image_xai(prompt: str) -> bytes | None:
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
        logger.warning(f"xAI image generation failed: {e}")
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
            _generate_image_openrouter,
        ),
        (config.google_api_key, "Google/gemini-2.5-flash", _generate_image_google),
        (config.openai_api_key, "OpenAI/gpt-image-1-mini", _generate_image_openai),
        (config.xai_api_key, "xAI/grok-imagine-image", _generate_image_xai),
    ]

    for api_key, provider_name, generate_fn in providers:
        if not api_key:
            continue
        logger.info(f"Generating avatar using {provider_name}")
        image_bytes = await generate_fn(prompt)
        if image_bytes:
            return image_bytes
        logger.warning(f"{provider_name} returned no image, trying next provider")

    logger.error("All image generation providers failed or none configured")
    return None


def _build_agent_profile(agent_id: str, agent: Any) -> str:
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


async def _generate_image_prompt(agent_id: str, agent: Any) -> str:
    """Use a cheap LLM to turn agent profile into an image generation prompt."""
    from intentkit.models.llm import create_llm_model
    from intentkit.models.llm_picker import pick_summarize_model

    profile = _build_agent_profile(agent_id, agent)

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = pick_summarize_model()
        llm = await create_llm_model(model_name, temperature=0.9)
        model = await llm.create_instance()

        response = await model.ainvoke(
            [
                SystemMessage(content=_AVATAR_SYSTEM_PROMPT),
                HumanMessage(content=f"Agent Profile:\n{profile}"),
            ]
        )
        image_prompt = response.content
        if not isinstance(image_prompt, str):
            image_prompt = str(image_prompt)

        logger.info(
            f"Generated avatar prompt for agent {agent_id}: {image_prompt[:200]}"
        )
        return image_prompt

    except Exception as e:
        logger.error(f"Failed to generate avatar prompt via LLM: {e}")
        # Fallback to a simple prompt derived from name
        name = getattr(agent, "name", None) or agent_id
        return (
            f"A modern, minimalist, professional AI avatar for an agent called '{name}'. "
            f"Abstract geometric design, vibrant gradient colors, clean lines, centered composition, no text."
        )


async def generate_avatar(agent_id: str, agent: Any) -> str | None:
    """Generate an avatar image for an agent and upload it to S3.

    Args:
        agent_id: The agent's unique identifier (used for the S3 storage path).
        agent: An agent-like object with prompt fields (Agent, AgentCreate, AgentUpdate, etc.).

    Returns:
        The image path without CDN prefix (e.g. "local/intentkit/avatars/{id}/xxx.png"),
        or None if generation failed.
    """
    # Step 1: Generate image prompt from agent profile
    image_prompt = await _generate_image_prompt(agent_id, agent)

    # Step 2: Generate image bytes
    image_bytes = await select_model_and_generate(image_prompt)
    if not image_bytes:
        return None

    # Step 3: Upload to S3
    try:
        from epyxid import XID

        key = f"avatars/{agent_id}/{XID()}.png"
        relative_path = await store_image_bytes(
            image_bytes, key, content_type="image/png"
        )

        if not relative_path:
            logger.error("store_image_bytes returned empty path")
            return None

        return relative_path
    except Exception as e:
        logger.error(f"Failed to upload avatar to S3: {e}")
        return None
