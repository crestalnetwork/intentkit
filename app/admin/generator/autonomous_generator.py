"""Autonomous Task Generator Module.

AI-based autonomous configuration generator for IntentKit agents.
Uses LLM to detect scheduling patterns and generate proper autonomous configurations.
"""

import json
import logging
import time
from typing import TYPE_CHECKING, List, Optional, Tuple

from epyxid import XID
from openai import OpenAI

from models.agent import AgentAutonomous
from skills import __all__ as available_skill_categories

if TYPE_CHECKING:
    from .llm_logger import LLMLogger

logger = logging.getLogger(__name__)


async def generate_autonomous_configuration(
    prompt: str,
    client: OpenAI,
    llm_logger: Optional["LLMLogger"] = None,
) -> Optional[Tuple[List[AgentAutonomous], List[str]]]:
    """Generate autonomous configuration from a prompt using AI.

    Args:
      prompt: The natural language prompt to analyze
      client: OpenAI client for LLM analysis
      llm_logger: Optional LLM logger for tracking API calls

    Returns:
      Tuple of (autonomous_configs, required_skills) if autonomous pattern detected,
      None otherwise
    """
    logger.info("Using AI to analyze prompt for autonomous patterns")
    logger.debug(
        f"Analyzing prompt: '{prompt[:100]}{'...' if len(prompt) > 100 else ''}'"
    )

    system_message = f"""You are an expert at analyzing user prompts to detect autonomous task patterns and generating IntentKit agent configurations.

TASK: Determine if the prompt describes a task that should run automatically on a schedule, and if so, generate the proper configuration.

AVAILABLE SKILLS: {", ".join(available_skill_categories)}

AUTONOMOUS FORMAT REQUIREMENTS:
- id: lowercase alphanumeric with dashes, max 20 chars (auto-generated)
- name: task display name, max 50 chars
- description: what the task does, max 200 chars 
- prompt: the actual command/prompt for the agent to execute, max 20,000 chars
- enabled: true
- schedule: EITHER "minutes" (integer) OR "cron" (string), minimum 5 minutes
- required_skills: list of skills needed from available skills

EXAMPLES OF AUTONOMOUS PATTERNS:
- "Create an agent that buys 0.1 eth every hour" → 60 minutes, needs "cdp" skill
- "Build a bot that posts tweets daily" → 1440 minutes, needs "twitter" skill 
- "Monitor my portfolio every 30 minutes" → 30 minutes, needs "portfolio" skill

EXAMPLES OF NON-AUTONOMOUS PATTERNS:
- "Create a trading bot" → general request, not specific scheduled task
- "Help me analyze crypto" → assistance request, not autonomous

RESPONSE FORMAT:
If autonomous pattern detected:
{{
 "has_autonomous": true,
 "autonomous_config": {{
  "name": "Brief task name",
  "description": "What this automation does", 
  "prompt": "Exact command to execute (no scheduling words)",
  "minutes": 60 // OR "cron": "0 * * * *"
 }},
 "required_skills": ["skill1", "skill2"]
}}

If no autonomous pattern:
{{
 "has_autonomous": false
}}

Be accurate and only detect true autonomous patterns with clear scheduling intent."""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Analyze this prompt: {prompt}"},
    ]

    try:
        logger.debug("Sending prompt to GPT-4 for autonomous pattern analysis")

        result_text = ""  # Initialize result_text

        # Log the LLM call if logger is provided
        if llm_logger:
            async with llm_logger.log_call(
                call_type="autonomous_pattern_analysis",
                prompt=prompt,
                retry_count=0,
                is_update=False,
                llm_model="gpt-4.1",
                openai_messages=messages,
            ) as call_log:
                call_start_time = time.time()

                try:
                    # Make OpenAI API call
                    response = client.chat.completions.create(
                        model="gpt-4.1",
                        messages=messages,
                        temperature=0.1,
                        max_tokens=500,
                    )
                except Exception as api_error:
                    logger.error(f"OpenAI API call failed: {api_error}")
                    raise api_error

                result_text = response.choices[0].message.content.strip()
                logger.debug(
                    f"GPT-4 response: {result_text[:200]}{'...' if len(result_text) > 200 else ''}"
                )

                # Log successful call
                await llm_logger.log_successful_call(
                    call_log=call_log,
                    response=response,
                    generated_content={"analysis_result": result_text},
                    openai_messages=messages,
                    call_start_time=call_start_time,
                )
        else:
            # Make call without logging (fallback)
            try:
                response = client.chat.completions.create(
                    model="gpt-4.1", messages=messages, temperature=0.1, max_tokens=500
                )
            except Exception as api_error:
                logger.error(f"OpenAI API call failed (no logger): {api_error}")
                raise api_error

            result_text = response.choices[0].message.content.strip()
            logger.debug(
                f"GPT-4 response: {result_text[:200]}{'...' if len(result_text) > 200 else ''}"
            )

        result = json.loads(result_text)

        if not result.get("has_autonomous", False):
            logger.info(" No autonomous pattern detected in prompt")
            return None

        logger.info(" Autonomous pattern detected! Processing configuration...")

        # Extract and validate configuration
        config_data = result["autonomous_config"]
        required_skills = result.get("required_skills", [])

        logger.info(f"Required skills for autonomous task: {required_skills}")

        # Validate required skills are available
        valid_skills = [
            skill for skill in required_skills if skill in available_skill_categories
        ]
        if len(valid_skills) != len(required_skills):
            invalid_skills = set(required_skills) - set(valid_skills)
            logger.warning(f"Some required skills not available: {invalid_skills}")
            logger.info(f"Valid skills that will be activated: {valid_skills}")
        else:
            logger.info(f"All required skills are available: {valid_skills}")

        # Generate autonomous configuration
        task_id = str(XID())[:10].lower()
        task_name = config_data["name"][:50]
        task_description = config_data["description"][:200]
        task_prompt = config_data["prompt"][:20000]

        autonomous_config = {
            "id": task_id,
            "name": task_name,
            "description": task_description,
            "prompt": task_prompt,
            "enabled": True,
        }

        # Set either minutes or cron, not both
        if config_data.get("minutes"):
            autonomous_config["minutes"] = max(
                5, int(config_data["minutes"])
            )  # Enforce minimum 5 minutes
            logger.info(f"Schedule: Every {autonomous_config['minutes']} minutes")
        elif config_data.get("cron"):
            cron_expr = config_data["cron"]
            autonomous_config["cron"] = cron_expr
            logger.info(f"Schedule: Cron expression '{cron_expr}'")
        else:
            logger.error(" No valid schedule provided in autonomous config")
            return None

        # Create AgentAutonomous object
        try:
            autonomous_obj = AgentAutonomous(**autonomous_config)
            schedule_info = (
                f"{autonomous_obj.minutes} minutes"
                if autonomous_obj.minutes
                else autonomous_obj.cron
            )
            logger.info(
                f"Generated autonomous task: '{autonomous_obj.name}' ({schedule_info})"
            )
            logger.info(f"Task details: {autonomous_obj.description}")
            logger.info(f"Task prompt: '{autonomous_obj.prompt}'")

            return [autonomous_obj], valid_skills
        except Exception as e:
            logger.error(f"Failed to create AgentAutonomous object: {e}")
            logger.debug(f"Config data that failed: {autonomous_config}")
            return None

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        if "result_text" in locals():
            logger.debug(f"Raw LLM response: {result_text}")
        return None
    except Exception as e:
        logger.error(f"LLM autonomous analysis failed: {e}")
        logger.debug(f"Error details: {str(e)}")
        return None
