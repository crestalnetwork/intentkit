"""Long-term memory management for agents."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from intentkit.models.agent_data import AgentData

logger = logging.getLogger(__name__)

_MEMORY_SYSTEM_PROMPT = """\
You are a memory manager. Your task is to merge existing memory with new information \
into a single consolidated memory document.

Rules:
- Keep total output under 4000 bytes.
- Use markdown with h3 (###) or lower headings only.
- Preserve important facts, remove redundant or outdated info.
- If new info contradicts old info, keep the new info.
- Output only the merged memory, no explanations or preamble."""

MAX_MEMORY_BYTES = 4000


async def update_memory(agent_id: str, new_content: str) -> str:
    """Merge new content into the agent's long-term memory using an LLM.

    Args:
        agent_id: The agent's ID.
        new_content: New information to merge into memory.

    Returns:
        The updated memory string.
    """
    from intentkit.models.llm import create_llm_model
    from intentkit.models.llm_picker import pick_summarize_model

    agent_data = await AgentData.get(agent_id)
    existing_memory = agent_data.long_term_memory or ""

    if existing_memory:
        user_msg = (
            f"### Existing Memory\n\n{existing_memory}\n\n"
            f"### New Information\n\n{new_content}"
        )
    else:
        user_msg = f"### New Information\n\n{new_content}"

    try:
        model_name = pick_summarize_model()
        llm = await create_llm_model(model_name, temperature=0.3)
        model = await llm.create_instance()

        response = await model.ainvoke(
            [
                SystemMessage(content=_MEMORY_SYSTEM_PROMPT),
                HumanMessage(content=user_msg),
            ]
        )
        result = response.content
        if not isinstance(result, str):
            result = str(result)
    except Exception as e:
        logger.error("LLM memory merge failed for agent %s: %s", agent_id, e)
        # Fallback: just append
        result = (
            f"{existing_memory}\n\n{new_content}".strip()
            if existing_memory
            else new_content
        )

    # Truncate to max bytes
    encoded = result.encode("utf-8")
    if len(encoded) > MAX_MEMORY_BYTES:
        result = encoded[:MAX_MEMORY_BYTES].decode("utf-8", errors="ignore")

    await AgentData.patch(agent_id, {"long_term_memory": result})

    # Lead agents (id format "team-{team_id}") are cached separately from
    # regular agents and the cache doesn't watch AgentData.updated_at, so we
    # must invalidate it explicitly here. This covers both the self-updater
    # path (lead_update_self_memory skill) and any direct call to the generic
    # update_memory system skill by the lead agent itself.
    if agent_id.startswith("team-"):
        from intentkit.core.lead.cache import invalidate_lead_cache

        invalidate_lead_cache(agent_id.removeprefix("team-"))

    return result
