"""Sync public agents from YAML files to database on startup.

This module provides a one-way sync mechanism that reads agent definitions
from the public_agents/ directory and upserts them into the database.
Agents are only updated when their content hash changes.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from yaml import safe_load

from intentkit.config.db import get_session
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent.user_input import AgentUpdate
from intentkit.models.llm import AVAILABLE_MODELS
from intentkit.models.team import TeamMemberTable, TeamRole, TeamTable
from intentkit.models.user import UserTable

logger = logging.getLogger(__name__)

PUBLIC_AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "public_agents"

OWNER = "predefined"
TEAM_ID = "predefined"


def _is_model_available(model_id: str) -> bool:
    """Check if a model is available in the current deployment."""
    if not model_id:
        return True  # Empty string triggers pick_default_model()
    if model_id in AVAILABLE_MODELS:
        return True
    # Check by bare model ID (AVAILABLE_MODELS is keyed by provider:id)
    return any(m.id == model_id for m in AVAILABLE_MODELS.values())


async def ensure_public_agent_prerequisites() -> None:
    """Ensure the predefined user/team and public virtual team exist."""
    try:
        async with get_session() as session:
            # Create "predefined" user
            predefined_user = await session.get(UserTable, "predefined")
            if not predefined_user:
                session.add(UserTable(id="predefined"))

            # Create "predefined" team
            predefined_team = await session.get(TeamTable, "predefined")
            if not predefined_team:
                session.add(TeamTable(id="predefined", name="predefined"))

            # Create "predefined" team membership
            predefined_member = await session.get(
                TeamMemberTable, {"team_id": "predefined", "user_id": "predefined"}
            )
            if not predefined_member:
                session.add(
                    TeamMemberTable(
                        team_id="predefined",
                        user_id="predefined",
                        role=TeamRole.OWNER,
                    )
                )

            # Create "public" virtual team
            public_team = await session.get(TeamTable, "public")
            if not public_team:
                session.add(TeamTable(id="public", name="public"))

            await session.commit()
    except Exception as e:
        logger.error("Failed to create public agent prerequisites: %s", e)


async def sync_public_agents() -> None:
    """Sync public agent YAML files to the database.

    For each YAML file in public_agents/:
    - If the agent doesn't exist in DB, create it
    - If the agent exists but content hash differs, update it
    - If the agent exists and hash matches, skip it
    """
    if not PUBLIC_AGENTS_DIR.exists():
        logger.info("No public_agents directory found, skipping sync")
        return

    yaml_files = sorted(PUBLIC_AGENTS_DIR.rglob("*.yaml"))
    if not yaml_files:
        logger.info("No YAML files found in public_agents/, skipping sync")
        return

    logger.info("Syncing %d public agent definitions...", len(yaml_files))

    # Parse and validate all YAML files first
    # Each entry: (slug, AgentUpdate, hash, description, tags)
    agents_to_sync: list[
        tuple[str, AgentUpdate, str, str | None, list[str] | None]
    ] = []
    for yaml_file in yaml_files:
        try:
            with open(yaml_file) as f:
                data = safe_load(f)
            if not data:
                logger.warning("Empty YAML file: %s", yaml_file.name)
                continue
            slug = data.get("slug") or yaml_file.stem
            agent_update = AgentUpdate.model_validate(data)
            # Hash from validated model ensures consistency with what gets written
            new_hash = agent_update.hash()
            # Fields on AgentTable but not AgentUpdate, extract separately
            description = data.get("description")
            tags = data.get("tags")
            agents_to_sync.append((slug, agent_update, new_hash, description, tags))
        except Exception:
            logger.exception("Failed to parse public agent from %s", yaml_file.name)

    if not agents_to_sync:
        return

    created = 0
    updated = 0
    skipped = 0
    archived = 0
    errors = 0

    async with get_session() as session:
        # Bulk-fetch all existing predefined agents
        result = await session.execute(
            select(AgentTable).where(AgentTable.owner == OWNER)
        )
        existing_by_slug: dict[str, AgentTable] = {}
        all_predefined: dict[str, AgentTable] = {}
        for a in result.scalars().all():
            all_predefined[a.id] = a
            if a.slug:
                existing_by_slug[a.slug] = a

        # Collect slugs we're syncing for archive detection
        syncing_slugs: set[str] = {a[0] for a in agents_to_sync}

        # Check for slug collisions with non-predefined agents
        slugs = [a[0] for a in agents_to_sync]
        predefined_ids = list(all_predefined.keys())
        if predefined_ids:
            slug_result = await session.execute(
                select(AgentTable.slug).where(
                    AgentTable.slug.in_(slugs),
                    AgentTable.id.notin_(predefined_ids),
                )
            )
        else:
            slug_result = await session.execute(
                select(AgentTable.slug).where(AgentTable.slug.in_(slugs))
            )
        taken_slugs: set[str] = {row[0] for row in slug_result.all() if row[0]}

        for slug, agent_update, new_hash, description, tags in agents_to_sync:
            existing = existing_by_slug.get(slug)
            model_available = _is_model_available(agent_update.model)

            if not model_available:
                if existing and existing.archived_at is None:
                    existing.archived_at = datetime.now(UTC)
                    logger.info(
                        "Archived public agent %s: model %s not available",
                        slug,
                        agent_update.model,
                    )
                elif not existing:
                    logger.info(
                        "Skipping public agent %s: model %s not available",
                        slug,
                        agent_update.model,
                    )
                skipped += 1
                continue

            if existing and existing.version == new_hash:
                # Un-archive if model became available again
                if existing.archived_at is not None:
                    existing.archived_at = None
                    logger.info("Un-archived public agent: %s", slug)
                skipped += 1
                continue

            update_data = agent_update.model_dump()

            if existing:
                for key, value in update_data.items():
                    setattr(existing, key, value)
                if description is not None:
                    existing.description = description
                if tags is not None:
                    existing.tags = tags
                existing.version = new_hash
                existing.deployed_at = func.now()
                existing.visibility = AgentVisibility.PUBLIC
                existing.archived_at = None  # Un-archive on update
                updated += 1
                logger.info("Updated public agent: %s (id=%s)", slug, existing.id)
            else:
                if slug in taken_slugs:
                    logger.warning(
                        "Slug '%s' already taken by another agent, skipping",
                        slug,
                    )
                    errors += 1
                    continue
                agent_id = f"public-{slug}"
                db_agent = AgentTable(**update_data)
                db_agent.id = agent_id
                db_agent.slug = slug
                db_agent.owner = OWNER
                db_agent.team_id = TEAM_ID
                db_agent.version = new_hash
                db_agent.deployed_at = func.now()
                db_agent.visibility = AgentVisibility.PUBLIC
                if description is not None:
                    db_agent.description = description
                if tags is not None:
                    db_agent.tags = tags
                session.add(db_agent)
                created += 1
                logger.info("Created public agent: %s (id=%s)", slug, agent_id)

        # Archive predefined agents whose slug is no longer in YAML files
        for agent in all_predefined.values():
            if agent.slug and agent.slug not in syncing_slugs:
                if agent.archived_at is None:
                    agent.archived_at = datetime.now(UTC)
                    archived += 1
                    logger.info(
                        "Archived removed public agent: %s (id=%s)",
                        agent.slug,
                        agent.id,
                    )

        # Collect agent IDs for auto-subscription before leaving the session.
        # ORM objects become detached after session close, so we capture IDs now.
        synced_agent_ids: list[str] = []
        for slug, _agent_update, _new_hash, _description, _tags in agents_to_sync:
            existing = existing_by_slug.get(slug)
            if existing:
                synced_agent_ids.append(existing.id)
            else:
                synced_agent_ids.append(f"public-{slug}")

        try:
            await session.commit()
        except Exception:
            logger.exception("Failed to commit public agents sync")
            await session.rollback()
            return

    # Auto-subscribe the "public" team to each synced agent
    from intentkit.core.team.subscription import auto_subscribe_team

    for agent_id in synced_agent_ids:
        try:
            await auto_subscribe_team("public", agent_id)
        except Exception:
            logger.exception("Failed to subscribe public team to %s", agent_id)

    logger.info(
        "Public agents sync complete: %d created, %d updated, %d skipped, %d archived, %d errors",
        created,
        updated,
        skipped,
        archived,
        errors,
    )
