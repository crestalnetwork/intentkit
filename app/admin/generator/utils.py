"""Utility functions for agent generation.

Common helper functions used across the generator modules.
"""

import json
import logging
import random
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
    """Generate tags using Crestal API and LLM selection."""

    # Simple fallback tags if everything fails - randomized to add variety
    def get_default_tags() -> List[Dict[str, int]]:
        fallback_sets = [
            [{"id": 28}, {"id": 23}, {"id": 20}],  # Analytics, Social Media, Automation
            [{"id": 3}, {"id": 11}, {"id": 53}],  # Trading, Gaming, API
            [
                {"id": 5},
                {"id": 14},
                {"id": 47},
            ],  # Investing, Content Creation, Security
            [
                {"id": 17},
                {"id": 27},
                {"id": 32},
            ],  # Personal Assistant, Marketing, Reporting
            [{"id": 33}, {"id": 43}, {"id": 38}],  # Art, Tutor, Fitness
            [{"id": 51}, {"id": 46}, {"id": 49}],  # DevOps, Research, Compliance
        ]

        # Add randomization based on current time
        random.seed(int(time.time()) % 10000)
        selected_set = random.choice(fallback_sets)

        logger.info(f"Using randomized fallback tags: {selected_set}")
        return selected_set

    try:
        # Use the fixed Crestal API endpoint
        crestal_api_url = "https://api.service.crestal.dev/v1/tags"
        logger.info(f"Fetching tags from Crestal API: {crestal_api_url}")

        # Get tags from Crestal API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(crestal_api_url)

            logger.info(f"Crestal API response status: {response.status_code}")

            if response.status_code != 200:
                logger.warning(
                    f"Crestal API returned status {response.status_code}: {response.text}"
                )
                return get_default_tags()

            tags_data = response.json()
            logger.info(
                f"Received {len(tags_data) if isinstance(tags_data, list) else 0} tags from Crestal API"
            )

            if not isinstance(tags_data, list) or len(tags_data) == 0:
                logger.warning("Crestal API response is not a valid list or is empty")
                return get_default_tags()

            # Group by category with tag IDs
            categories = {}
            tag_lookup = {}  # name -> {id, name, category}

            for tag in tags_data:
                # Handle the actual Crestal API response format
                cat = tag.get("category", "")
                name = tag.get("name", "")
                tag_id = tag.get("id")

                if cat and name and tag_id:
                    # Clean up category name (decode \u0026 to &)
                    clean_category = cat.replace("\\u0026", "&")

                    if clean_category not in categories:
                        categories[clean_category] = []
                    categories[clean_category].append(name)
                    tag_lookup[name] = {
                        "id": tag_id,
                        "name": name,
                        "category": clean_category,
                    }

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
        logger.warning("Crestal API request timed out")
        return get_default_tags()
    except httpx.ConnectError:
        logger.warning("Could not connect to Crestal API")
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

        random_seed = int(time.time() * 1000) % 10000
        random.seed(random_seed)

        # Shuffle categories
        category_items = list(categories.items())
        random.shuffle(category_items)

        # Build category info for prompt
        cat_info = []
        for cat_name, tag_list in category_items:
            # Also shuffle tags within each category
            shuffled_tags = tag_list.copy()
            random.shuffle(shuffled_tags)
            cat_info.append(f"{cat_name}: {', '.join(shuffled_tags)}")

        # Add randomization elements to make prompt more unique
        variation_phrases = [
            "Based on the agent's characteristics, identify the most suitable tags",
            "Analyze the agent's purpose and skills to determine appropriate tags",
            "Consider the agent's functionality and select relevant tags",
            "Evaluate the agent's capabilities and choose fitting tags",
        ]

        selected_phrase = random.choice(variation_phrases)

        timestamp_hash = abs(hash(str(time.time()))) % 1000

        llm_prompt = f"""{selected_phrase} from the available categories below.

Agent Configuration:
- Name: {agent_schema.get("name", "AI Agent")}
- Purpose: {agent_schema.get("purpose", "Not specified")}
- Skills: {", ".join(agent_schema.get("skills", {}).keys()) or "None specified"}
- User Request: {prompt}
- Session ID: {timestamp_hash}

Available Tag Categories:
{chr(10).join(cat_info)}

Instructions:
- Select exactly 3 tag names from DIFFERENT categories
- Prioritize tags that best match the agent's purpose and skills
- Return response as a JSON array of tag names
- Example format: ["Trading", "Social Media", "Analytics"]
- Avoid selecting tags from the same category

Your selection:"""

        logger.info("Calling OpenAI for tag selection with randomized prompt")

        # Increase temperature for more diverse outputs
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": llm_prompt}],
            temperature=0.8,
            max_tokens=150,
            top_p=0.9,
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
        selected_categories = set()

        for tag in selected_tags:
            if tag in all_tag_names and len(valid_tags) < 3:
                # Find the category of this tag
                tag_category = None
                for cat_name, tag_list in categories.items():
                    if tag in tag_list:
                        tag_category = cat_name
                        break

                # Only add if from a different category (for diversity)
                if tag_category and tag_category not in selected_categories:
                    valid_tags.append(tag)
                    selected_categories.add(tag_category)
                    logger.info(f"Added tag '{tag}' from category '{tag_category}'")
                elif tag_category in selected_categories:
                    logger.info(
                        f"Skipped tag '{tag}' - category '{tag_category}' already selected"
                    )
            elif tag not in all_tag_names:
                logger.warning(f"Tag '{tag}' not found in available tags")

        if len(valid_tags) < 3:
            unused_categories = [
                cat for cat in categories.keys() if cat not in selected_categories
            ]
            random.shuffle(unused_categories)

            for cat_name in unused_categories:
                if len(valid_tags) >= 3:
                    break
                available_tags = categories[cat_name]
                if available_tags:
                    random_tag = random.choice(available_tags)
                    valid_tags.append(random_tag)
                    selected_categories.add(cat_name)
                    logger.info(
                        f"Added random tag '{random_tag}' from unused category '{cat_name}'"
                    )

        logger.info(
            f"Final valid tags after filtering and diversification: {valid_tags}"
        )
        return valid_tags[:3]  # Ensure exactly 3 tags

    except Exception as e:
        logger.error(f"Error in LLM tag selection: {str(e)}")
        return []
