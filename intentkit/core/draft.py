"""Service functions for agent draft operations."""

from __future__ import annotations

from epyxid import XID
from fastapi import status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.core.agent import get_agent
from intentkit.models.agent import AgentUserInput
from intentkit.models.draft import AgentDraft, AgentDraftTable
from intentkit.utils.error import IntentKitAPIError


async def update_agent_draft(
    *,
    agent_id: str,
    user_id: str,
    input: AgentUserInput,
    db: AsyncSession,
) -> AgentDraft:
    """Update the latest draft for the specified agent with partial field updates.

    This function only updates fields that are explicitly provided in the input,
    leaving other fields unchanged. This is more efficient than override as it
    reduces context usage and minimizes the risk of accidentally changing fields.
    """
    query = (
        select(AgentDraftTable)
        .where(AgentDraftTable.agent_id == agent_id, AgentDraftTable.owner == user_id)
        .order_by(desc(AgentDraftTable.created_at))
        .limit(1)
    )

    result = await db.execute(query)
    latest_draft = result.scalar_one_or_none()

    if not latest_draft:
        raise IntentKitAPIError(
            status.HTTP_404_NOT_FOUND,
            "DraftNotFound",
            "No drafts found for this agent",
        )

    # Get only the fields that are explicitly provided (exclude_unset=True)
    update_data = input.model_dump(exclude_unset=True)

    if latest_draft.deployed_at is not None:
        # Create new draft version if current one is deployed
        draft_id = str(XID())

        # Start with existing draft data and merge updates
        draft_data = AgentUserInput.model_validate(latest_draft).model_dump()
        draft_data.update(update_data)

        updated_input = AgentUserInput.model_validate(draft_data)

        draft_table = AgentDraftTable(
            id=draft_id,
            agent_id=agent_id,
            owner=user_id,
            version=updated_input.hash(),
            last_draft_id=latest_draft.id,
            project_id=latest_draft.project_id,
            **draft_data,
        )

        db.add(draft_table)
        await db.commit()
        await db.refresh(draft_table)

        return AgentDraft.model_validate(draft_table)

    # Update existing draft in-place
    for key, value in update_data.items():
        setattr(latest_draft, key, value)

    # Update version hash based on updated data
    updated_input = AgentUserInput.model_validate(latest_draft)
    latest_draft.version = updated_input.hash()

    await db.commit()
    await db.refresh(latest_draft)

    return AgentDraft.model_validate(latest_draft)


async def override_agent_draft(
    *,
    agent_id: str,
    user_id: str,
    input: AgentUserInput,
    db: AsyncSession,
) -> AgentDraft:
    """Override the latest draft for the specified agent."""
    query = (
        select(AgentDraftTable)
        .where(AgentDraftTable.agent_id == agent_id, AgentDraftTable.owner == user_id)
        .order_by(desc(AgentDraftTable.created_at))
        .limit(1)
    )

    result = await db.execute(query)
    latest_draft = result.scalar_one_or_none()

    if not latest_draft:
        raise IntentKitAPIError(
            status.HTTP_404_NOT_FOUND,
            "DraftNotFound",
            "No drafts found for this agent",
        )

    if latest_draft.deployed_at is not None:
        draft_id = str(XID())

        draft_table = AgentDraftTable(
            id=draft_id,
            agent_id=agent_id,
            owner=user_id,
            version=input.hash(),
            last_draft_id=latest_draft.id,
            project_id=latest_draft.project_id,
            **input.model_dump(),
        )

        db.add(draft_table)
        await db.commit()
        await db.refresh(draft_table)

        return AgentDraft.model_validate(draft_table)

    for key, value in input.model_dump().items():
        setattr(latest_draft, key, value)

    latest_draft.version = input.hash()

    await db.commit()
    await db.refresh(latest_draft)

    return AgentDraft.model_validate(latest_draft)


async def get_agent_latest_draft(
    *,
    agent_id: str,
    user_id: str,
    db: AsyncSession,
) -> AgentDraft:
    """Return the latest draft for the specified agent."""
    query = (
        select(AgentDraftTable)
        .where(AgentDraftTable.agent_id == agent_id, AgentDraftTable.owner == user_id)
        .order_by(desc(AgentDraftTable.created_at))
        .limit(1)
    )

    result = await db.execute(query)
    latest_draft = result.scalar_one_or_none()

    if latest_draft:
        return AgentDraft.model_validate(latest_draft)

    agent = await get_agent(agent_id)

    if not agent:
        raise IntentKitAPIError(
            status.HTTP_404_NOT_FOUND,
            "AgentNotFound",
            "No drafts found for this agent",
        )

    if agent.owner != user_id:
        raise IntentKitAPIError(
            status.HTTP_403_FORBIDDEN,
            "Forbidden",
            "Not your agent",
        )

    draft_id = str(XID())

    agent_dict = agent.model_dump()
    input_dict: dict[str, object] = {}
    for key in AgentUserInput.model_fields:
        if key in agent_dict:
            input_dict[key] = agent_dict[key]
    input = AgentUserInput.model_validate(input_dict)

    draft_table = AgentDraftTable(
        id=draft_id,
        agent_id=agent_id,
        owner=user_id,
        version=input.hash(),
        deployed_at=agent.updated_at,
        **input.model_dump(),
    )

    db.add(draft_table)
    await db.commit()
    await db.refresh(draft_table)

    return AgentDraft.model_validate(draft_table)
