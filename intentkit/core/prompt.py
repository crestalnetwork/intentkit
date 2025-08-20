import re
from typing import Callable, Optional

from eth_utils import is_address
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.runtime import Runtime

from intentkit.abstracts.graph import AgentContext, AgentState
from intentkit.config.config import config
from intentkit.models.agent import Agent
from intentkit.models.agent_data import AgentData
from intentkit.models.chat import AuthorType
from intentkit.models.skill import Skill

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

# Base system prompt components
BASE_SYSTEM_PROMPT = """You are an AI agent built using IntentKit.
Your tools are called 'skills'.
If your skill fails to execute due to a technical error ask the user to try again later, don't retry by yourself. If someone asks you to do something you can't do with your currently available skills, you must say so, recommend them to submit their feedback to the IntentKit team at https://github.com/crestalnetwork/intentkit. Be concise and helpful with your responses."""

ENSO_SKILLS_GUIDE = """## ENSO Skills Guide

You are integrated with the Enso API. You can use enso_get_tokens to retrieve token information,
including APY, Protocol Slug, Symbol, Address, Decimals, and underlying tokens. When interacting with token amounts,
ensure to multiply input amounts by the token's decimal places and divide output amounts by the token's decimals. 
Utilize enso_route_shortcut to find the best swap or deposit route. Set broadcast_request to True only when the 
user explicitly requests a transaction broadcast. Insufficient funds or insufficient spending approval can cause 
Route Shortcut broadcasts to fail. To avoid this, use the enso_broadcast_wallet_approve tool that requires explicit 
user confirmation before broadcasting any approval transactions for security reasons.

"""


# ============================================================================
# CORE PROMPT BUILDING FUNCTIONS
# ============================================================================


def _build_system_header() -> str:
    """Build the system prompt header."""
    prompt = "# SYSTEM PROMPT\n\n"
    if config.system_prompt:
        prompt += config.system_prompt + "\n\n"
    prompt += BASE_SYSTEM_PROMPT + "\n"
    return prompt


def _build_agent_identity_section(agent: Agent) -> str:
    """Build agent identity information section."""
    identity_parts = []

    if agent.name:
        identity_parts.append(f"Your name is {agent.name}.")
    if agent.ticker:
        identity_parts.append(f"Your ticker symbol is {agent.ticker}.")

    return "\n".join(identity_parts) + ("\n" if identity_parts else "")


def _build_social_accounts_section(agent_data: AgentData) -> str:
    """Build social accounts information section."""
    if not agent_data:
        return ""

    social_parts = []

    # Twitter info
    if agent_data.twitter_id:
        social_parts.append(
            f"Your twitter id is {agent_data.twitter_id}, never reply or retweet yourself."
        )
    if agent_data.twitter_username:
        social_parts.append(f"Your twitter username is {agent_data.twitter_username}.")
    if agent_data.twitter_name:
        social_parts.append(f"Your twitter name is {agent_data.twitter_name}.")

    # Twitter verification status
    if agent_data.twitter_is_verified:
        social_parts.append("Your twitter account is verified.")
    else:
        social_parts.append("Your twitter account is not verified.")

    # Telegram info
    if agent_data.telegram_id:
        social_parts.append(f"Your telegram bot id is {agent_data.telegram_id}.")
    if agent_data.telegram_username:
        social_parts.append(
            f"Your telegram bot username is {agent_data.telegram_username}."
        )
    if agent_data.telegram_name:
        social_parts.append(f"Your telegram bot name is {agent_data.telegram_name}.")

    return "\n".join(social_parts) + ("\n" if social_parts else "")


def _build_wallet_section(agent: Agent, agent_data: AgentData) -> str:
    """Build wallet information section."""
    if not agent_data:
        return ""

    wallet_parts = []
    network_id = agent.network_id or agent.cdp_network_id

    if agent_data.evm_wallet_address and network_id != "solana":
        wallet_parts.append(
            f"Your wallet address in {network_id} is {agent_data.evm_wallet_address}."
        )
    if agent_data.solana_wallet_address and network_id == "solana":
        wallet_parts.append(
            f"Your wallet address in {network_id} is {agent_data.solana_wallet_address}."
        )

    return "\n".join(wallet_parts) + ("\n" if wallet_parts else "")


def _build_user_info_section(context: AgentContext) -> str:
    """Build user information section when user_id is a valid EVM wallet address."""
    if not context.user_id:
        return ""

    # Check if user_id is a valid EVM wallet address
    try:
        if is_address(context.user_id):
            return f"## User Info\n\nThe person you are talking to has wallet address: {context.user_id}\n\n"
    except Exception:
        # If validation fails, don't include the section
        pass

    return ""


def _build_agent_characteristics_section(agent: Agent) -> str:
    """Build agent characteristics section (purpose, personality, principles, etc.)."""
    sections = []

    if agent.purpose:
        sections.append(f"## Purpose\n\n{agent.purpose}")
    if agent.personality:
        sections.append(f"## Personality\n\n{agent.personality}")
    if agent.principles:
        sections.append(f"## Principles\n\n{agent.principles}")
    if agent.prompt:
        sections.append(f"## Initial Rules\n\n{agent.prompt}")

    return "\n\n".join(sections) + ("\n\n" if sections else "")


def _build_skills_guides_section(agent: Agent) -> str:
    """Build skills-specific guides section."""
    guides = []

    # ENSO skills guide
    if agent.skills and "enso" in agent.skills and agent.skills["enso"].get("enabled"):
        guides.append(ENSO_SKILLS_GUIDE)

    return "".join(guides)


def build_agent_prompt(agent: Agent, agent_data: AgentData) -> str:
    """
    Build the complete agent system prompt.

    This function orchestrates the building of different prompt sections:
    - System header and base prompt
    - Agent identity (name, ticker)
    - Social accounts (Twitter, Telegram)
    - Wallet information
    - Agent characteristics (purpose, personality, principles)
    - Skills-specific guides

    Args:
        agent: The agent configuration
        agent_data: The agent's runtime data

    Returns:
        str: The complete system prompt
    """
    prompt_sections = [
        _build_system_header(),
        _build_agent_identity_section(agent),
        _build_social_accounts_section(agent_data),
        _build_wallet_section(agent, agent_data),
        "\n",  # Add spacing before characteristics
        _build_agent_characteristics_section(agent),
        _build_skills_guides_section(agent),
    ]

    return "".join(section for section in prompt_sections if section)


# Legacy function name for backward compatibility
def agent_prompt(agent: Agent, agent_data: AgentData) -> str:
    """Legacy function name. Use build_agent_prompt instead."""
    return build_agent_prompt(agent, agent_data)


async def explain_prompt(message: str) -> str:
    """
    Process message to replace @skill:*:* patterns with (call skill xxxxx) format.
    This function is used when admin_llm_skill_control is enabled.

    Args:
        message (str): The input message to process

    Returns:
        str: The processed message with @skill patterns replaced
    """
    # Pattern to match @skill:category:config_name with word boundaries
    pattern = r"\b@skill:([^:]+):([^\s]+)\b"

    async def replace_skill_pattern(match):
        category = match.group(1)
        config_name = match.group(2)

        # Get skill by category and config_name
        skill = await Skill.get_by_config_name(category, config_name)

        if skill:
            return f"(call skill {skill.name})"
        else:
            # If skill not found, keep original pattern
            return match.group(0)

    # Find all matches
    matches = list(re.finditer(pattern, message))

    # Process matches in reverse order to maintain string positions
    result = message
    for match in reversed(matches):
        replacement = await replace_skill_pattern(match)
        result = result[: match.start()] + replacement + result[match.end() :]

    return result


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def escape_prompt(prompt: str) -> str:
    """Escape curly braces in the prompt for template processing."""
    return prompt.replace("{", "{{").replace("}", "}}")


# ============================================================================
# ENTRYPOINT PROCESSING FUNCTIONS
# ============================================================================


def _build_autonomous_task_prompt(agent: Agent, context: AgentContext) -> str:
    """Build prompt for autonomous task entrypoint."""
    task_id = context.chat_id.removeprefix("autonomous-")

    # Find the autonomous task by task_id
    autonomous_task = None
    if agent.autonomous:
        for task in agent.autonomous:
            if task.id == task_id:
                autonomous_task = task
                break

    if not autonomous_task:
        # Fallback if task not found
        return f"You are running an autonomous task. The task id is {task_id}. "

    # Build detailed task info - always include task_id
    if autonomous_task.name:
        task_info = f"You are running an autonomous task '{autonomous_task.name}' (ID: {task_id})"
    else:
        task_info = f"You are running an autonomous task (ID: {task_id})"

    # Add description if available
    if autonomous_task.description:
        task_info += f": {autonomous_task.description}"

    # Add cycle info
    if autonomous_task.minutes:
        task_info += f". This task runs every {autonomous_task.minutes} minute(s)"
    elif autonomous_task.cron:
        task_info += f". This task runs on schedule: {autonomous_task.cron}"

    return f"{task_info}. "


async def build_entrypoint_prompt(agent: Agent, context: AgentContext) -> Optional[str]:
    """
    Build entrypoint-specific prompt based on context.

    Supports different entrypoint types:
    - Telegram: Uses agent.telegram_entrypoint_prompt
    - Autonomous tasks: Builds task-specific prompt with scheduling info

    Args:
        agent: The agent configuration
        context: The agent context containing entrypoint information

    Returns:
        Optional[str]: The entrypoint-specific prompt, or None if no entrypoint
    """
    if not context.entrypoint:
        return None

    entrypoint = context.entrypoint
    entrypoint_prompt = None

    # Handle social media entrypoints
    if entrypoint == AuthorType.TELEGRAM.value:
        if config.tg_system_prompt:
            entrypoint_prompt = "\n\n" + config.tg_system_prompt
        if agent.telegram_entrypoint_prompt:
            entrypoint_prompt = "\n\n" + agent.telegram_entrypoint_prompt
    elif entrypoint == AuthorType.XMTP.value:
        if config.xmtp_system_prompt:
            entrypoint_prompt = "\n\n" + config.xmtp_system_prompt
        if agent.xmtp_entrypoint_prompt:
            entrypoint_prompt = "\n\n" + agent.xmtp_entrypoint_prompt
    elif entrypoint == AuthorType.TRIGGER.value:
        entrypoint_prompt = "\n\n" + _build_autonomous_task_prompt(agent, context)

    # Process with admin LLM skill control if enabled
    if entrypoint_prompt and config.admin_llm_skill_control:
        entrypoint_prompt = await explain_prompt(entrypoint_prompt)

    return entrypoint_prompt


def build_internal_info_prompt(context: AgentContext) -> str:
    """Build internal info prompt with context information."""
    internal_info = "## Internal Info\n\n"
    internal_info += "These are for your internal use. You can use them when querying or storing data, "
    internal_info += "but please do not directly share this information with users.\n\n"
    internal_info += f"chat_id: {context.chat_id}\n\n"
    if context.user_id:
        internal_info += f"user_id: {context.user_id}\n\n"
    return internal_info


# ============================================================================
# MAIN PROMPT FACTORY FUNCTION
# ============================================================================


def create_formatted_prompt_function(agent: Agent, agent_data: AgentData) -> Callable:
    """
    Create the formatted_prompt function with agent-specific configuration.

    This is the main factory function that creates a prompt formatting function
    tailored to a specific agent. The returned function will be used by the
    agent's runtime to format prompts for each conversation.

    Args:
        agent: The agent configuration
        agent_data: The agent's runtime data

    Returns:
        Callable: An async function that formats prompts based on agent state and context
    """
    # Build base prompt using the new function name
    prompt = build_agent_prompt(agent, agent_data)
    escaped_prompt = escape_prompt(prompt)

    # Process with admin LLM skill control if enabled
    async def get_base_prompt():
        if config.admin_llm_skill_control:
            return await explain_prompt(escaped_prompt)
        return escaped_prompt

    # Build prompt array
    prompt_array = [
        ("placeholder", "{system_prompt}"),
        ("placeholder", "{messages}"),
    ]

    if agent.prompt_append:
        # Escape any curly braces in prompt_append
        escaped_append = escape_prompt(agent.prompt_append)
        prompt_array.append(("system", escaped_append))

    prompt_temp = ChatPromptTemplate.from_messages(prompt_array)

    async def formatted_prompt(
        state: AgentState, runtime: Runtime[AgentContext]
    ) -> list[BaseMessage]:
        # Get base prompt (with potential admin LLM skill control processing)
        final_system_prompt = await get_base_prompt()

        context = runtime.context

        # Add entrypoint prompt if applicable
        entrypoint_prompt = await build_entrypoint_prompt(agent, context)
        if entrypoint_prompt:
            final_system_prompt = (
                f"{final_system_prompt}## Entrypoint rules{entrypoint_prompt}\n\n"
            )

        # Add user info if user_id is a valid EVM wallet address
        user_info = _build_user_info_section(context)
        if user_info:
            final_system_prompt = f"{final_system_prompt}{user_info}"

        # Add internal info
        internal_info = build_internal_info_prompt(context)
        final_system_prompt = f"{final_system_prompt}{internal_info}"

        # Process prompt_append with admin LLM skill control if needed
        if agent.prompt_append and config.admin_llm_skill_control:
            # Find the system message in prompt_array and process it
            for i, (role, content) in enumerate(prompt_array):
                if role == "system":
                    processed_append = await explain_prompt(content)
                    prompt_array[i] = ("system", processed_append)
                    break

        system_prompt = [("system", final_system_prompt)]
        return prompt_temp.invoke(
            {
                "messages": state["messages"],
                "system_prompt": system_prompt,
            }
        )

    return formatted_prompt
