import logging
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.db import get_session
from intentkit.models.agent import Agent, AgentCreate, AgentUpdate
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent_data import AgentData
from intentkit.utils.error import IntentKitAPIError

from .info import invalidate_agent_info
from .notifications import send_agent_notification
from .publish import (
    ensure_not_referenced_by_public_agent,
    ensure_sub_agents_public,
    is_public_visibility,
)
from .queries import get_agent, get_agent_by_id_or_slug
from .tool_registry import filter_wallet_tool_names, sanitize_tools, validate_tools

logger = logging.getLogger(__name__)


def _invalidate_lead_for_team(team_id: str | None) -> None:
    """Drop the team lead's cached prompt after an agent mutation.

    The lead's system prompt embeds the team's agent roster (each agent's
    name, slug, and description), so edits to those fields must invalidate the
    lead cache or the roster shows stale text until the cache TTL. Invalidating
    here — at the patch/override funnel — covers every field-editing caller
    (the lead's own tool and the REST patch/override endpoints) without each
    one remembering to. The import is deferred to avoid a core.agent ->
    core.lead cycle at module load.
    """
    if not team_id:
        return
    from intentkit.core.lead.cache import invalidate_lead_cache

    invalidate_lead_cache(team_id)


async def _validate_wallet_tools(tools: list[str] | None, team_id: str | None) -> None:
    """Reject wallet-operating tools for teams that own no wallets.

    Wallet tools operate on team wallets; without at least one wallet they
    can never run, so they are not selectable. Web3-themed tools that only
    read on-chain or market data carry no such requirement.
    """
    if not tools:
        return
    wallet_names = filter_wallet_tool_names(tools)
    if not wallet_names:
        return
    from intentkit.models.wallet import TeamWallet, wallet_owner_team

    wallets = await TeamWallet.list_for_team(wallet_owner_team(team_id))
    if not wallets:
        raise IntentKitAPIError(
            400,
            # Key predates the web3/wallet flag split; kept for API stability.
            "Web3ToolsRequireWallet",
            "This team has no crypto wallets, so wallet-operating web3 tools "
            "cannot be enabled. Create a wallet first in the Crypto Wallets "
            "page.",
        )


async def _validate_slug_unique(
    slug: str, exclude_agent_id: str | None, db: AsyncSession
) -> None:
    """Check that a slug is not already in use by another agent."""
    query = select(AgentTable.id).where(AgentTable.slug == slug)
    if exclude_agent_id:
        query = query.where(AgentTable.id != exclude_agent_id)
    existing = await db.scalar(query)
    if existing:
        raise IntentKitAPIError(
            400, "SlugAlreadyExists", f"Slug '{slug}' is already in use"
        )


async def _validate_sub_agents(sub_agents: list[str]) -> None:
    """Validate that all sub-agents exist.

    Routing text is intentionally not required: the sub-agents prompt section
    uses the optional public ``description``, and requiring it would block
    wiring existing agents that never set one.
    """
    for agent_ref in sub_agents:
        target = await get_agent_by_id_or_slug(agent_ref)
        if not target:
            raise IntentKitAPIError(
                400,
                "InvalidSubAgent",
                f"Sub-agent '{agent_ref}' not found",
            )


async def _ensure_visibility_invariants(
    agent_id: str,
    existing_agent: Agent,
    *,
    new_visibility: int | AgentVisibility | None,
    new_sub_agents: list[str] | None,
    new_archived_at: datetime | None,
    new_slug: str | None,
    visibility_changing: bool,
    sub_agents_changing: bool,
) -> None:
    """A live public agent may only reference public sub-agents, and an agent
    referenced by a live public agent cannot be hidden or archived.

    Covers every transition reachable through override/patch: becoming
    public, editing sub_agents while public, un-archiving back into a live
    public agent, leaving public, and archiving.
    """
    self_refs = {ref for ref in (agent_id, existing_agent.slug, new_slug) if ref}
    was_public = is_public_visibility(existing_agent.visibility)
    will_be_public = is_public_visibility(new_visibility)
    was_archived = existing_agent.archived_at is not None
    will_be_archived = new_archived_at is not None
    unarchiving = was_archived and not will_be_archived

    if (
        will_be_public
        and not will_be_archived
        and (visibility_changing or sub_agents_changing or unarchiving)
    ):
        await ensure_sub_agents_public(new_sub_agents, exclude=self_refs)

    becomes_hidden = was_public and visibility_changing and not will_be_public
    archiving = will_be_archived and not was_archived
    if becomes_hidden or archiving:
        await ensure_not_referenced_by_public_agent(agent_id, existing_agent.slug)


async def override_agent(
    agent_id: str, agent: AgentUpdate, owner: str | None = None
) -> tuple[Agent, AgentData]:
    """Override an existing agent with new configuration.

    This function updates an existing agent with the provided configuration.
    If some fields are not provided, they will be reset to default values.

    Args:
        agent_id: ID of the agent to override
        agent: Agent update configuration containing the new settings
        owner: Optional owner for permission validation

    Returns:
        tuple[Agent, AgentData]: Updated agent configuration and processed agent data

    Raises:
        IntentKitAPIError:
            - 404: Agent not found
            - 403: Permission denied (if owner mismatch)
            - 400: Invalid configuration or wallet provider change
    """
    existing_agent = await get_agent(agent_id)
    if not existing_agent:
        raise IntentKitAPIError(
            status_code=404,
            key="AgentNotFound",
            message=f"Agent with ID '{agent_id}' not found",
        )
    if owner and owner != existing_agent.owner:
        raise IntentKitAPIError(403, "Forbidden", "forbidden")

    # Validate sub-agents if present
    if agent.sub_agents:
        await _validate_sub_agents(agent.sub_agents)

    # Slug immutability check
    if (
        existing_agent.slug
        and agent.slug is not None
        and agent.slug != existing_agent.slug
    ):
        raise IntentKitAPIError(400, "SlugImmutable", "Slug cannot be changed once set")

    # Wallet-operating tools are only usable when the team owns a wallet
    await _validate_wallet_tools(agent.tools, existing_agent.team_id)

    # Visibility invariants (override replaces every field)
    await _ensure_visibility_invariants(
        agent_id,
        existing_agent,
        new_visibility=agent.visibility,
        new_sub_agents=agent.sub_agents,
        new_archived_at=agent.archived_at,
        new_slug=agent.slug,
        visibility_changing=True,
        sub_agents_changing=True,
    )

    async with get_session() as db:
        db_agent = await db.get(AgentTable, agent_id)
        if not db_agent:
            raise IntentKitAPIError(
                status_code=404,
                key="AgentNotFound",
                message="Agent not found",
            )

        # Slug uniqueness check
        if agent.slug:
            await _validate_slug_unique(agent.slug, agent_id, db)

        # update
        update_data = agent.model_dump()
        if "tools" in update_data and update_data["tools"]:
            update_data["tools"] = sanitize_tools(update_data["tools"])
        for key, value in update_data.items():
            setattr(db_agent, key, value)
        # version
        db_agent.version = agent.hash()
        await db.commit()
        await db.refresh(db_agent)
        latest_agent = Agent.model_validate(db_agent)

    await invalidate_agent_info(agent_id)
    _invalidate_lead_for_team(latest_agent.team_id)
    agent_data = await AgentData.get(agent_id)
    send_agent_notification(latest_agent, agent_data, "Agent Overridden")

    return latest_agent, agent_data


async def patch_agent(
    agent_id: str, agent: AgentUpdate, owner: str | None = None
) -> tuple[Agent, AgentData]:
    """Patch an existing agent with partial updates.

    This function updates an existing agent with only the fields that are provided.
    Fields that are not specified will remain unchanged.

    Args:
        agent_id: ID of the agent to patch
        agent: Agent update configuration containing only the fields to update
        owner: Optional owner for permission validation

    Returns:
        tuple[Agent, AgentData]: Updated agent configuration and processed agent data

    Raises:
        IntentKitAPIError:
            - 404: Agent not found
            - 403: Permission denied (if owner mismatch)
            - 400: Invalid configuration or wallet provider change
    """
    existing_agent = await get_agent(agent_id)
    if not existing_agent:
        raise IntentKitAPIError(
            status_code=404,
            key="AgentNotFound",
            message=f"Agent with ID '{agent_id}' not found",
        )
    if owner and owner != existing_agent.owner:
        raise IntentKitAPIError(403, "Forbidden", "forbidden")

    # Validate sub-agents if present in update
    update_fields = agent.model_dump(exclude_unset=True)
    if "sub_agents" in update_fields and update_fields["sub_agents"]:
        await _validate_sub_agents(update_fields["sub_agents"])

    # Slug immutability check
    if (
        existing_agent.slug
        and "slug" in update_fields
        and update_fields["slug"] != existing_agent.slug
    ):
        raise IntentKitAPIError(400, "SlugImmutable", "Slug cannot be changed once set")

    # Wallet-operating tools are only usable when the team owns a wallet
    if "tools" in update_fields:
        await _validate_wallet_tools(update_fields["tools"], existing_agent.team_id)

    # Visibility invariants (patch changes only the provided fields)
    await _ensure_visibility_invariants(
        agent_id,
        existing_agent,
        new_visibility=update_fields.get("visibility", existing_agent.visibility),
        new_sub_agents=update_fields.get("sub_agents", existing_agent.sub_agents),
        new_archived_at=update_fields.get("archived_at", existing_agent.archived_at),
        new_slug=update_fields.get("slug"),
        visibility_changing="visibility" in update_fields,
        sub_agents_changing="sub_agents" in update_fields,
    )

    async with get_session() as db:
        db_agent = await db.get(AgentTable, agent_id)
        if not db_agent:
            raise IntentKitAPIError(
                status_code=404,
                key="AgentNotFound",
                message="Agent not found",
            )

        # Slug uniqueness check
        slug_value = update_fields.get("slug")
        if slug_value:
            await _validate_slug_unique(slug_value, agent_id, db)

        # update
        update_data = update_fields
        if "tools" in update_data and update_data["tools"]:
            update_data["tools"] = sanitize_tools(update_data["tools"])
        for key, value in update_data.items():
            setattr(db_agent, key, value)
        db_agent.version = agent.hash()
        await db.commit()
        await db.refresh(db_agent)
        latest_agent = Agent.model_validate(db_agent)

    await invalidate_agent_info(agent_id)
    _invalidate_lead_for_team(latest_agent.team_id)
    agent_data = await AgentData.get(agent_id)
    send_agent_notification(latest_agent, agent_data, "Agent Patched")

    return latest_agent, agent_data


async def create_agent(agent: AgentCreate) -> tuple[Agent, AgentData]:
    """Create a new agent with the provided configuration.

    This function creates a new agent instance with the given configuration,
    initializes its wallet, and sends a notification about the creation.

    Args:
        agent: Agent creation configuration containing all necessary settings

    Returns:
        tuple[Agent, AgentData]: Created agent configuration and processed agent data

    Raises:
        IntentKitAPIError:
            - 400: Agent with upstream ID already exists or invalid configuration
            - 500: Database error or wallet initialization failure
    """
    if not agent.owner:
        agent.owner = "system"
    # Check for existing agent by upstream_id, forward compatibility, raise error after 3.0
    if agent.upstream_id:
        async with get_session() as db:
            existing = await db.scalar(
                select(AgentTable).where(AgentTable.upstream_id == agent.upstream_id)
            )
            if existing:
                raise IntentKitAPIError(
                    status_code=400,
                    key="BadRequest",
                    message="Agent with this upstream ID already exists",
                )

    # Validate sub-agents if present
    if agent.sub_agents:
        await _validate_sub_agents(agent.sub_agents)

    # An agent born public may only reference public sub-agents
    if is_public_visibility(agent.visibility):
        await ensure_sub_agents_public(
            agent.sub_agents, exclude={agent.slug} if agent.slug else None
        )

    # Validate tools configuration
    if agent.tools:
        validate_tools(agent.tools)

    # Wallet-operating tools are only usable when the team owns a wallet
    await _validate_wallet_tools(agent.tools, agent.team_id)

    async with get_session() as db:
        try:
            # Slug uniqueness check
            if agent.slug:
                await _validate_slug_unique(agent.slug, None, db)

            create_data = agent.model_dump()
            db_agent = AgentTable(**create_data)
            db_agent.version = agent.hash()
            db.add(db_agent)
            await db.commit()
            await db.refresh(db_agent)
            latest_agent = Agent.model_validate(db_agent)
        except IntegrityError:
            await db.rollback()
            raise IntentKitAPIError(
                status_code=400,
                key="AgentExists",
                message=f"Agent with ID '{agent.id}' already exists",
            )

    # A lookup before creation may have negative-cached this id.
    await invalidate_agent_info(latest_agent.id)
    agent_data = await AgentData.get(latest_agent.id)
    send_agent_notification(latest_agent, agent_data, "Agent Created")

    if latest_agent.team_id:
        try:
            from intentkit.core.team.subscription import auto_subscribe_team

            await auto_subscribe_team(latest_agent.team_id, latest_agent.id)
        except Exception:
            logger.exception(
                "Failed to auto-subscribe team %s to agent %s",
                latest_agent.team_id,
                latest_agent.id,
            )

    return latest_agent, agent_data


async def backfill_agent_avatar(agent_id: str) -> None:
    """Generate an avatar for an agent and write it back if still empty.

    Intended to be scheduled as a background task after agent create/override/
    patch. No-ops (and swallows all errors) if the agent is gone, already has a
    picture, or the generation/upload fails.
    """
    # Deferred import: intentkit.core.avatar pulls in heavy optional deps
    # (PIL, google.genai, openai) that would otherwise load on every cold
    # start of any service importing core.agent.
    from intentkit.core.avatar import generate_avatar

    async with get_session() as db:
        db_agent = await db.get(AgentTable, agent_id)
        if not db_agent or db_agent.picture:
            return
        agent_snapshot = Agent.model_validate(db_agent)

    try:
        avatar_path = await generate_avatar(agent_id, agent_snapshot)
    except Exception as e:
        logger.warning("Agent avatar backfill generate failed for %s: %s", agent_id, e)
        return
    if not avatar_path:
        return

    try:
        async with get_session() as db:
            # Match both NULL and empty-string so a prior PATCH that cleared the
            # column to "" still gets backfilled; the scheduling sites treat
            # empty string as missing, and the write must agree.
            await db.execute(
                update(AgentTable)
                .where(
                    AgentTable.id == agent_id,
                    or_(AgentTable.picture.is_(None), AgentTable.picture == ""),
                )
                .values(picture=avatar_path)
            )
            await db.commit()
        await invalidate_agent_info(agent_id)
    except Exception as e:
        logger.warning("Agent avatar backfill write failed for %s: %s", agent_id, e)
