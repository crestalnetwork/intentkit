"""Sync public agents from Markdown files to database on startup.

This module provides a one-way sync mechanism that reads agent definitions
from the public_agents/ directory and upserts them into the database.
Agents are only updated when their content hash changes.

Each definition is a Markdown file with YAML frontmatter: the frontmatter holds
the agent's configuration, and everything after it is the system prompt. The
prompt is the overwhelming majority of every file, so it gets to be plain
Markdown rather than a quoted YAML block scalar.

    ---
    name: Translator
    slug: translator
    ---

    ## Purpose

    ...

Unknown frontmatter keys are rejected rather than ignored: ``AgentUpdate``
silently drops extras, which is how a removed field (``temperature``) once sat
in these files unnoticed, and how a typo like ``slugg:`` would quietly fall back
to the filename.
"""

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from intentkit.config.db import get_session
from intentkit.models.agent.core import AgentVisibility
from intentkit.models.agent.db import AgentTable
from intentkit.models.agent.user_input import AgentUpdate
from intentkit.models.llm import is_model_resolvable
from intentkit.models.team import TeamMemberTable, TeamRole, TeamTable
from intentkit.models.user import UserTable
from intentkit.utils.yaml import safe_load

logger = logging.getLogger(__name__)

PUBLIC_AGENTS_DIR = Path(__file__).resolve().parent.parent.parent / "public_agents"

OWNER = "predefined"
TEAM_ID = "predefined"


def _is_model_available(model_id: str) -> bool:
    """Check if a model resolves in the current deployment.

    Uses the same resolution as ``LLMModelInfo.get`` so base-name and
    ``legacy_ids`` routing count as available — anything the runtime would
    resolve must not get a public agent archived here.
    """
    if not model_id:
        return True  # Empty string triggers pick_default_model()
    return is_model_resolvable(model_id)


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


async def _warn_if_referenced(agent_id: str, slug: str | None) -> None:
    """Log (never block) when archiving a predefined agent breaks references."""
    from intentkit.core.agent.publish import ensure_not_referenced_by_public_agent
    from intentkit.utils.error import IntentKitAPIError

    try:
        await ensure_not_referenced_by_public_agent(agent_id, slug)
    except IntentKitAPIError as e:
        logger.warning(
            "Archiving predefined agent %s strands public references: %s",
            agent_id,
            e.message,
        )


# Each entry: (slug, AgentUpdate, hash, tags)
_SyncEntry = tuple[str, AgentUpdate, str, list[str] | None]

# Frontmatter keys that are not AgentUpdate fields but are still ours to read.
# `tags` lives on AgentTable; the sync applies it separately.
_EXTRA_FRONTMATTER_KEYS = frozenset({"tags"})

_FRONTMATTER_DELIMITER = "---"


def parse_agent_markdown(text: str, *, source: str) -> dict:
    """Parse one agent definition into a dict of agent fields.

    The document is YAML frontmatter followed by the system prompt::

        ---
        name: Translator
        ---

        ## Purpose
        ...

    Raises ``ValueError`` on anything malformed. Unknown frontmatter keys are an
    error, not a silent drop -- that is the whole point of parsing strictly here
    rather than handing the dict straight to ``AgentUpdate``.
    """
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise ValueError(f"{source}: must start with a '---' frontmatter block")

    try:
        closing = next(
            i
            for i in range(1, len(lines))
            if lines[i].strip() == _FRONTMATTER_DELIMITER
        )
    except StopIteration:
        raise ValueError(f"{source}: frontmatter block is never closed") from None

    frontmatter = safe_load("\n".join(lines[1:closing])) or {}
    if not isinstance(frontmatter, dict):
        # Malformed file content, not a wrong argument type — ValueError keeps
        # it consistent with the sibling frontmatter checks.
        raise ValueError(f"{source}: frontmatter must be a mapping")  # noqa: TRY004

    allowed = set(AgentUpdate.model_fields) | _EXTRA_FRONTMATTER_KEYS
    unknown = sorted(set(frontmatter) - allowed)
    if unknown:
        raise ValueError(f"{source}: unknown frontmatter keys: {', '.join(unknown)}")
    if "system_prompt" in frontmatter:
        raise ValueError(
            f"{source}: system_prompt comes from the document body, "
            "it must not be set in the frontmatter"
        )

    system_prompt = "\n".join(lines[closing + 1 :]).strip()
    if not system_prompt:
        raise ValueError(f"{source}: the body (system prompt) is empty")

    return {**frontmatter, "system_prompt": system_prompt}


def _collect_agents_to_sync() -> list[_SyncEntry]:
    """Scan public_agents/ and parse every definition into a sync entry.

    Runs in a worker thread: the directory walk, the file reads and the pydantic
    validation are all blocking. A file that fails to parse is logged and
    skipped so one bad definition cannot abort the whole sync.
    """
    if not PUBLIC_AGENTS_DIR.exists():
        logger.info("No public_agents directory found, skipping sync")
        return []

    agent_files = sorted(PUBLIC_AGENTS_DIR.rglob("*.md"))
    if not agent_files:
        logger.info("No agent definitions found in public_agents/, skipping sync")
        return []

    logger.info("Syncing %d public agent definitions...", len(agent_files))

    entries: list[_SyncEntry] = []
    for agent_file in agent_files:
        try:
            data = parse_agent_markdown(agent_file.read_text(), source=agent_file.name)
            slug = data.get("slug") or agent_file.stem
            agent_update = AgentUpdate.model_validate(data)
            # Hash from validated model ensures consistency with what gets written
            new_hash = agent_update.hash()
            # Fields on AgentTable but not AgentUpdate, extract separately
            tags = data.get("tags")
            entries.append((slug, agent_update, new_hash, tags))
        except Exception:
            logger.exception("Failed to parse public agent from %s", agent_file.name)
    return entries


async def sync_public_agents() -> None:
    """Sync public agent definitions to the database.

    For each Markdown file in public_agents/:
    - If the agent doesn't exist in DB, create it
    - If the agent exists but content hash differs, update it
    - If the agent exists and hash matches, skip it
    """
    agents_to_sync = await asyncio.to_thread(_collect_agents_to_sync)

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

        for slug, agent_update, new_hash, tags in agents_to_sync:
            existing = existing_by_slug.get(slug)
            model_available = _is_model_available(agent_update.model)

            if not model_available:
                if existing and existing.archived_at is None:
                    # System-curated agents are exempt from the visibility
                    # invariants (they define their own world), but
                    # archiving one may strand user agents that reference it.
                    await _warn_if_referenced(existing.id, existing.slug)
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
                if tags is not None:
                    existing.tags = tags
                existing.version = new_hash
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
                db_agent.visibility = AgentVisibility.PUBLIC
                if tags is not None:
                    db_agent.tags = tags
                session.add(db_agent)
                created += 1
                logger.info("Created public agent: %s (id=%s)", slug, agent_id)

        # Archive predefined agents whose slug no longer has a definition file
        for agent in all_predefined.values():
            if (
                agent.slug
                and agent.slug not in syncing_slugs
                and agent.archived_at is None
            ):
                await _warn_if_referenced(agent.id, agent.slug)
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
        for slug, _agent_update, _new_hash, _tags in agents_to_sync:
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
