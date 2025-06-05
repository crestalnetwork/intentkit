"""Utility functions for agent generation.

Common helper functions used across the generator modules.
"""

import json
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

import httpx
from epyxid import XID
from openai import OpenAI

from app.config.config import config

if TYPE_CHECKING:
    from .llm_logger import LLMLogger

logger = logging.getLogger(__name__)


def extract_token_usage(response) -> Dict[str, Any]:
    """Extract token usage information from OpenAI response.

    Args:
        response: OpenAI API response

    Returns:
        Dict containing token usage information
    """
    usage_info = {
        "total_tokens": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "input_tokens_details": None,
        "completion_tokens_details": None,
    }

    if hasattr(response, "usage") and response.usage:
        usage = response.usage
        usage_info["total_tokens"] = getattr(usage, "total_tokens", 0)
        usage_info["input_tokens"] = getattr(usage, "prompt_tokens", 0) or getattr(
            usage, "input_tokens", 0
        )
        usage_info["output_tokens"] = getattr(usage, "completion_tokens", 0) or getattr(
            usage, "output_tokens", 0
        )

        # Get detailed token information if available
        if hasattr(usage, "input_tokens_details") and usage.input_tokens_details:
            usage_info["input_tokens_details"] = (
                usage.input_tokens_details.__dict__
                if hasattr(usage.input_tokens_details, "__dict__")
                else dict(usage.input_tokens_details)
            )

            # Extract cached input tokens for cost calculation
            if isinstance(usage_info["input_tokens_details"], dict):
                usage_info["cached_input_tokens"] = usage_info[
                    "input_tokens_details"
                ].get("cached_tokens", 0)

        if (
            hasattr(usage, "completion_tokens_details")
            and usage.completion_tokens_details
        ):
            usage_info["completion_tokens_details"] = (
                usage.completion_tokens_details.__dict__
                if hasattr(usage.completion_tokens_details, "__dict__")
                else dict(usage.completion_tokens_details)
            )

    return usage_info


def generate_request_id() -> str:
    """Generate a unique request ID for grouping related conversations."""
    return str(XID())


async def generate_agent_summary(
    schema: Dict[str, Any],
    identified_skills: Set[str],
    client: OpenAI,
    llm_logger: Optional["LLMLogger"] = None,
) -> str:
    """Generate a human-readable summary of the created agent.

    Args:
        schema: The generated agent schema
        identified_skills: Skills identified for the agent
        client: OpenAI client for API calls
        llm_logger: Optional LLM logger for tracking API calls

    Returns:
        Human-readable summary message
    """
    logger.info("Generating agent summary message")

    # Create skills list
    skills_list = (
        ", ".join(identified_skills) if identified_skills else "general capabilities"
    )

    # Get agent attributes
    agent_name = schema.get("name", "AI Agent")
    agent_purpose = schema.get("purpose", "assist users with various tasks")

    # Prepare messages for summary generation
    messages = [
        {
            "role": "system",
            "content": """You are writing a congratulatory message for a user who just generated an AI agent.
            
Write a friendly, enthusiastic message that:
1. Congratulates them on creating their agent
2. Mentions the agent's name and main purpose
3. Lists the key capabilities (skills) the agent has
4. Keeps it concise (1-2 sentences)

Make it sound exciting and helpful, like "Congratulations! You've successfully created [AgentName], an AI agent that can [purpose] with capabilities including [skills]. Your agent is ready to help you [brief benefit]!"

Be specific about the agent's abilities but keep the tone conversational and encouraging.""",
        },
        {
            "role": "user",
            "content": f"""Agent created:
Name: {agent_name}
Purpose: {agent_purpose}
Skills: {skills_list}

Write a congratulatory message.""",
        },
    ]

    # Log the LLM call if logger is provided
    if llm_logger:
        async with llm_logger.log_call(
            call_type="agent_summary_generation",
            prompt=f"Generate summary for agent: {agent_name}",
            retry_count=0,
            is_update=False,
            llm_model="gpt-4.1-nano",
            openai_messages=messages,
        ) as call_log:
            call_start_time = time.time()

            # Make OpenAI API call
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=messages,
                temperature=0.7,
                max_tokens=300,
            )

            # Extract generated content
            summary = response.choices[0].message.content.strip()

            generated_content = {
                "summary": summary,
                "agent_name": agent_name,
                "skills": list(identified_skills),
            }

            # Log successful call
            await llm_logger.log_successful_call(
                call_log=call_log,
                response=response,
                generated_content=generated_content,
                openai_messages=messages,
                call_start_time=call_start_time,
            )

            return summary
    else:
        # Make call without logging (fallback)
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=messages,
            temperature=0.7,
            max_tokens=300,
        )

        summary = response.choices[0].message.content.strip()
        return summary


# List of allowed models
ALLOWED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1-nano",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o4-mini",
    "deepseek-chat",
    "grok-2",
    "grok-3",
    "grok-3-mini",
    "eternalai",
    "reigent",
    "venice-uncensored",
    "venice-llama-4-maverick-17b",
]


async def generate_tags_from_nation_api(
    agent_schema: Dict[str, Any], prompt: str
) -> List[Dict[str, int]]:
    """Generate tags using Nation API and LLM selection."""

    # Simple fallback tags if everything fails
    def get_default_tags() -> List[Dict[str, int]]:
        return [
            {"id": 28},
            {"id": 23},
            {"id": 20},
        ]  # Analytics, Social Media, Automation

    if not config.nation_api_url:
        logger.info("Nation API URL not configured, using default tags")
        return get_default_tags()

    try:
        logger.info(f"Fetching tags from Nation API: {config.nation_api_url}/v1/tags")

        # Get tags from Nation API
        headers = {}
        if config.nation_api_key:
            headers["Authorization"] = f"Bearer {config.nation_api_key}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{config.nation_api_url}/v1/tags", headers=headers
            )

            logger.info(f"Nation API response status: {response.status_code}")

            if response.status_code != 200:
                logger.warning(
                    f"Nation API returned status {response.status_code}: {response.text}"
                )
                return get_default_tags()

            tags_data = response.json()
            logger.info(
                f"Received {len(tags_data) if isinstance(tags_data, list) else 0} tags from Nation API"
            )

            if not isinstance(tags_data, list) or len(tags_data) == 0:
                logger.warning("Nation API response is not a valid list or is empty")
                return get_default_tags()

            # Group by category with tag IDs
            categories = {}
            tag_lookup = {}  # name -> {id, name, category}

            for tag in tags_data:
                cat = tag.get("category", "")
                name = tag.get("name", "")
                tag_id = tag.get("id")

                if cat and name and tag_id:
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(name)
                    tag_lookup[name] = {"id": tag_id, "name": name, "category": cat}

            logger.info(
                f"Grouped tags into {len(categories)} categories: {list(categories.keys())}"
            )

            if not categories:
                logger.warning("No valid categories found after processing tags")
                return get_default_tags()

            # Use LLM to select tag names, then convert to IDs
            selected_names = await select_tags_with_llm(
                agent_schema, prompt, categories
            )
            logger.info(f"LLM selected tag names: {selected_names}")

            if not selected_names:
                logger.warning("LLM returned no tag names")
                return get_default_tags()

            # Convert names to ID objects for frontend
            selected_tags = []
            for name in selected_names:
                if name in tag_lookup:
                    selected_tags.append({"id": tag_lookup[name]["id"]})
                    logger.info(
                        f"Converted tag '{name}' to ID {tag_lookup[name]['id']}"
                    )
                else:
                    logger.warning(f"Tag name '{name}' not found in lookup table")

            if len(selected_tags) < 3:
                logger.warning(
                    f"Only got {len(selected_tags)} valid tags, using defaults"
                )
                return get_default_tags()

            # Return exactly 3 tags
            final_tags = selected_tags[:3]
            logger.info(f"Final selected tags (3 max): {final_tags}")
            return final_tags

    except httpx.TimeoutException:
        logger.warning("Nation API request timed out")
        return get_default_tags()
    except httpx.ConnectError:
        logger.warning("Could not connect to Nation API")
        return get_default_tags()
    except Exception as e:
        logger.error(f"Error in tag generation: {str(e)}")
        return get_default_tags()


async def select_tags_with_llm(
    agent_schema: Dict[str, Any], prompt: str, categories: Dict[str, List[str]]
) -> List[str]:
    """Use LLM to select appropriate tag names."""
    try:
        if not config.openai_api_key:
            logger.warning("OpenAI API key not configured")
            return []

        client = OpenAI(api_key=config.openai_api_key)

        # Build category info for prompt
        cat_info = []
        for cat_name, tag_list in categories.items():
            cat_info.append(f"{cat_name}: {', '.join(tag_list)}")

        llm_prompt = f"""Select exactly 3 most relevant tags from different categories for this agent:

Agent: {agent_schema.get("name", "AI Agent")}
Purpose: {agent_schema.get("purpose", "")}
Skills: {", ".join(agent_schema.get("skills", {}).keys())}
Prompt: {prompt}

Categories:
{chr(10).join(cat_info)}

Return exactly 3 tag names as a JSON array from different categories. Example: ["Trading", "Social Media", "Analytics"]"""

        logger.info("Calling OpenAI for tag selection")

        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": llm_prompt}],
            temperature=0.3,
            max_tokens=100,
        )

        result = response.choices[0].message.content.strip()
        logger.info(f"LLM raw response: {result}")

        try:
            selected_tags = json.loads(result)
            logger.info(f"Parsed LLM response: {selected_tags}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response was: {result}")
            return []

        # Validate tags exist in categories and limit to 3
        valid_tags = []
        all_tag_names = [tag for tags in categories.values() for tag in tags]
        for tag in selected_tags:
            if tag in all_tag_names and len(valid_tags) < 3:
                valid_tags.append(tag)
            elif tag not in all_tag_names:
                logger.warning(f"Tag '{tag}' not found in available tags")

        logger.info(f"Valid tags after filtering (max 3): {valid_tags}")
        return valid_tags

    except Exception as e:
        logger.error(f"Error in LLM tag selection: {str(e)}")
        return []
