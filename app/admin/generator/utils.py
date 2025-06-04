"""Utility functions for agent generation.

Common helper functions used across the generator modules.
"""

import logging
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, Set

from epyxid import XID
from openai import OpenAI

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
