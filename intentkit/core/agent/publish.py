"""Publish / unpublish helpers for team-owned agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, or_, select

from intentkit.config.db import get_session
from intentkit.core.agent.public_info import apply_public_info_update
from intentkit.models.agent import AgentPublicInfo, AgentTable
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.team import TeamTable
from intentkit.models.team_feed import TeamSubscriptionTable
from intentkit.utils.error import IntentKitAPIError

if TYPE_CHECKING:
    from intentkit.models.agent import Agent


def is_public_visibility(visibility: int | AgentVisibility | None) -> bool:
    return visibility is not None and visibility >= AgentVisibility.PUBLIC


async def ensure_sub_agents_public(
    sub_agents: list[str] | None, *, exclude: set[str] | None = None
) -> None:
    """Every referenced sub-agent must itself be public (and alive).

    A public agent's call_agent is usable by guests, so a hidden sub-agent
    reachable through it would leak across the visibility boundary.

    Best-effort validation: it runs in its own transaction, so a concurrent
    visibility flip can slip past it (same trade-off as the pre-existing
    ``_validate_sub_agents``; the no-FK convention rules out DB enforcement).

    Raises:
        IntentKitAPIError 400 ``SubAgentsNotPublic`` listing offending refs.
    """
    if not sub_agents:
        return
    exclude = exclude or set()
    not_public: list[str] = []
    async with get_session() as session:
        for ref in dict.fromkeys(sub_agents):  # dedup, keep order
            if ref in exclude:
                continue
            rows = (
                (
                    await session.execute(
                        select(AgentTable).where(
                            or_(AgentTable.id == ref, AgentTable.slug == ref)
                        )
                    )
                )
                .scalars()
                .all()
            )
            # Id takes priority over slug, mirroring runtime resolution
            # (get_agent_by_id_or_slug): a ref could match one agent's id
            # and another agent's slug.
            row = next((r for r in rows if r.id == ref), rows[0] if rows else None)
            if (
                row is None
                or row.archived_at is not None
                or not is_public_visibility(row.visibility)
            ):
                not_public.append(ref)
    if not_public:
        raise IntentKitAPIError(
            400,
            "SubAgentsNotPublic",
            "All sub-agents of a public agent must be public themselves. "
            f"Not public: {', '.join(not_public)}",
        )


async def ensure_not_referenced_by_public_agent(
    agent_id: str, slug: str | None = None
) -> None:
    """Refuse hiding/archiving/deleting an agent a public agent delegates to.

    Sub-agent references may use the agent's id or its slug; both are checked.
    Best-effort validation (own transaction; see ``ensure_sub_agents_public``).

    Raises:
        IntentKitAPIError 409 ``ReferencedByPublicAgent``.
    """
    refs = [agent_id] + ([slug] if slug else [])
    async with get_session() as session:
        stmt = (
            select(AgentTable.id, AgentTable.name)
            .where(
                AgentTable.visibility >= AgentVisibility.PUBLIC,
                AgentTable.archived_at.is_(None),
                AgentTable.id != agent_id,
                or_(*[AgentTable.sub_agents.contains([ref]) for ref in refs]),
            )
            .order_by(AgentTable.id)
            .limit(5)
        )
        rows = (await session.execute(stmt)).all()
    if rows:
        names = ", ".join(str(name or row_id) for row_id, name in rows)
        raise IntentKitAPIError(
            409,
            "ReferencedByPublicAgent",
            "This agent is a sub-agent of public agent(s) and cannot be "
            f"hidden, archived, or deleted while referenced: {names}",
        )


async def publish_agent(
    *,
    agent_id: str,
    public_info: AgentPublicInfo,
    description: str | None = None,
) -> "Agent":
    """Mark an agent as public after merging in the supplied public info.

    Enforces the owning team's ``public_agent_limit`` before flipping
    visibility. Only fields explicitly provided in ``public_info`` are written
    so callers can update a single field (matches ``update_public_info``).
    ``description`` is a core agent field collected by the publish form, so
    it is written here alongside the public info when provided.

    Raises:
        IntentKitAPIError 404: agent missing.
        IntentKitAPIError 400: agent has no team_id, or a sub-agent is not
            public (``SubAgentsNotPublic``).
        IntentKitAPIError 403: team has reached its public_agent_limit.
    """
    from intentkit.models.agent import Agent

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()
        if not db_agent:
            raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

        if not db_agent.team_id:
            raise IntentKitAPIError(
                400,
                "AgentHasNoTeam",
                "Only team-owned agents can be published",
            )

        self_refs = {ref for ref in (db_agent.id, db_agent.slug) if ref}
        await ensure_sub_agents_public(db_agent.sub_agents, exclude=self_refs)

        # Re-publishing an already public agent is allowed and bypasses the
        # quota check so operators can update public_info without losing
        # access to their own existing slot.
        is_already_public = is_public_visibility(db_agent.visibility)

        if not is_already_public:
            # SELECT FOR UPDATE on the team row serializes concurrent publishes
            # against the same team so the limit can't be exceeded by a race
            # between two simultaneous quota checks.
            team = await session.get(TeamTable, db_agent.team_id, with_for_update=True)
            if team is None:
                raise IntentKitAPIError(
                    404, "TeamNotFound", f"Team {db_agent.team_id} not found"
                )

            current_public_count = (
                await session.scalar(
                    select(func.count(AgentTable.id)).where(
                        AgentTable.team_id == db_agent.team_id,
                        AgentTable.visibility >= AgentVisibility.PUBLIC,
                        AgentTable.archived_at.is_(None),
                    )
                )
                or 0
            )

            if current_public_count >= team.public_agent_limit:
                raise IntentKitAPIError(
                    403,
                    "PublicAgentLimitReached",
                    f"Team has reached its public agent limit ({team.public_agent_limit})",
                )

        apply_public_info_update(db_agent, public_info)
        if description is not None:
            db_agent.description = description
        db_agent.visibility = AgentVisibility.PUBLIC
        team_id = db_agent.team_id

        await session.commit()
        await session.refresh(db_agent)

        # Publishing can rewrite the description, which the team lead's injected
        # roster renders — drop the lead cache so it isn't stale. Deferred
        # import avoids a core.agent -> core.lead cycle at module load.
        from intentkit.core.lead.cache import invalidate_lead_cache

        invalidate_lead_cache(team_id)

        return Agent.model_validate(db_agent)


async def unpublish_agent(*, agent_id: str) -> "Agent":
    """Flip an agent back to TEAM visibility and clear its subscriptions.

    Activity / post feed rows are intentionally retained. Only the
    ``team_subscriptions`` rows are cleared so the agent stops appearing on
    subscriber timelines going forward.

    Raises:
        IntentKitAPIError 404: agent missing.
        IntentKitAPIError 409: a live public agent references this agent.
    """
    from intentkit.models.agent import Agent

    async with get_session() as session:
        result = await session.execute(
            select(AgentTable).where(AgentTable.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()
        if not db_agent:
            raise IntentKitAPIError(404, "NotFound", f"Agent {agent_id} not found")

        await ensure_not_referenced_by_public_agent(db_agent.id, db_agent.slug)

        db_agent.visibility = AgentVisibility.TEAM

        await session.execute(
            delete(TeamSubscriptionTable).where(
                TeamSubscriptionTable.agent_id == agent_id
            )
        )

        await session.commit()
        await session.refresh(db_agent)

        return Agent.model_validate(db_agent)
