import importlib
from collections.abc import AsyncGenerator

from sqlalchemy import select

from intentkit.config.db import get_session
from intentkit.core.agent.constants import ENS_NAME_PATTERN
from intentkit.models.agent import Agent, AgentTable
from intentkit.utils.ens import resolve_ens_to_address


async def get_agent(agent_id: str) -> Agent | None:
    """Get an agent by ID and render with template if template_id exists.

    This function retrieves an agent from the database and applies template
    rendering if the agent has a template_id set.

    Args:
        agent_id: The unique identifier of the agent

    Returns:
        Agent | None: The agent with template applied if applicable, or None if not found
    """
    async with get_session() as db:
        item = await db.scalar(select(AgentTable).where(AgentTable.id == agent_id))
        if item is None:
            return None
        agent = Agent.model_validate(item)

    if item.template_id:
        template_module = importlib.import_module("intentkit.core.template")
        render_agent = template_module.render_agent
        agent = await render_agent(agent)

    return agent


async def iterate_agent_id_batches(
    batch_size: int = 100,
) -> AsyncGenerator[list[str], None]:
    """Yield agent IDs in ascending batches to limit memory usage."""

    last_id: str | None = None
    while True:
        async with get_session() as session:
            query = select(AgentTable.id).order_by(AgentTable.id)

            if last_id:
                query = query.where(AgentTable.id > last_id)

            query = query.limit(batch_size)
            result = await session.execute(query)
            agent_ids = [row[0] for row in result]

        if not agent_ids:
            break

        yield agent_ids
        last_id = agent_ids[-1]


async def get_agent_by_id_or_slug(agent_id: str) -> Agent | None:
    """Get agent by ID or slug and render with template if template_id exists.

    First tries to get by ID if agent_id length <= 20,
    then falls back to searching by slug if not found.

    Args:
        agent_id: Agent ID or slug to search for

    Returns:
        Agent | None: The agent with template applied if applicable, or None if not found
    """
    query_id = agent_id
    if ENS_NAME_PATTERN.fullmatch(agent_id):
        query_id = await resolve_ens_to_address(agent_id)

    async with get_session() as db:
        item = None

        if len(query_id) <= 20 or query_id.startswith("0x"):
            item = await db.scalar(select(AgentTable).where(AgentTable.id == query_id))

        if item is None:
            slug_stmt = select(AgentTable).where(AgentTable.slug == query_id)
            item = await db.scalar(slug_stmt)

        if item is None:
            return None

        agent = Agent.model_validate(item)

    if item.template_id:
        template_module = importlib.import_module("intentkit.core.template")
        render_agent = template_module.render_agent
        agent = await render_agent(agent)

    return agent
