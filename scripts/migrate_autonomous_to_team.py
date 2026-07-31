#!/usr/bin/env python3
"""One-time migration: move per-agent autonomous tasks to the team-owned
``autonomous_tasks`` table.

For each task embedded in ``agents.autonomous`` (JSONB):
- ``team_id``        = the agent's ``team_id`` (skipped with a warning if absent)
- ``target_agent_id``= the agent's id (preserves direct execution on that agent)
- ``minutes`` is converted to ``cron``; other fields and runtime status/next_run_time
  are preserved.

The autonomous service runs :func:`migrate_if_table_empty` automatically at
startup, so per-environment manual runs are not needed. Running this script
directly forces the migration regardless of existing rows (still idempotent:
inserts use ``ON CONFLICT (id) DO NOTHING``).

Remove this script (and the ``agents.autonomous`` column, and the startup hook
in ``app/autonomous.py``) after a few releases.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text

from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.models.autonomous import minutes_to_cron

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


_INSERT = text(
    """
    INSERT INTO autonomous_tasks
        (id, team_id, target_agent_id, name, description, cron, prompt,
         enabled, status, next_run_time)
    VALUES
        (:id, :team_id, :target_agent_id, :name, :description, :cron, :prompt,
         :enabled, :status, :next_run_time)
    ON CONFLICT (id) DO NOTHING
    """
)


def _resolve_cron(task: dict[str, Any]) -> str | None:
    cron = task.get("cron")
    if cron:
        return cron
    minutes = task.get("minutes")
    # minutes_to_cron normalizes 0/negative to a 5-minute schedule, matching the
    # old behavior, so convert whenever minutes is present (including 0).
    if minutes is not None:
        try:
            return minutes_to_cron(int(minutes))
        except (TypeError, ValueError):
            # The legacy JSONB is schema-less; a malformed minutes value must
            # not fail the whole batch — treat the task as unscheduled.
            logger.warning("Invalid minutes value %r; treating as no schedule", minutes)
            return None
    return None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def build_task_rows(
    agent_rows: list[tuple[str, str | None, list[dict[str, Any]] | None]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build ``autonomous_tasks`` insert rows from agent autonomous JSON.

    Pure transformation (no DB), so it can be unit-tested. Returns the rows to
    insert plus counters describing what was migrated or skipped.
    """
    rows: list[dict[str, Any]] = []
    stats = {"migrated": 0, "skipped_no_team": 0, "skipped_no_cron": 0}

    for agent_id, team_id, autonomous in agent_rows:
        if not autonomous:
            continue
        if not team_id:
            stats["skipped_no_team"] += len(autonomous)
            logger.warning(
                "Agent %s has %d task(s) but no team_id; skipping",
                agent_id,
                len(autonomous),
            )
            continue

        for task in autonomous:
            task_id = task.get("id")
            if not task_id:
                logger.warning("Agent %s has a task without id; skipping", agent_id)
                continue

            cron = _resolve_cron(task)
            if not cron:
                stats["skipped_no_cron"] += 1
                logger.warning(
                    "Task %s (agent %s) has no cron/minutes; skipping",
                    task_id,
                    agent_id,
                )
                continue

            enabled = task.get("enabled")
            rows.append(
                {
                    "id": task_id,
                    "team_id": team_id,
                    "target_agent_id": agent_id,
                    "name": task.get("name"),
                    "description": task.get("description"),
                    "cron": cron,
                    "prompt": task.get("prompt") or "",
                    "enabled": True if enabled is None else bool(enabled),
                    "status": task.get("status"),
                    "next_run_time": _parse_dt(task.get("next_run_time")),
                }
            )
            stats["migrated"] += 1

    return rows, stats


async def migrate():
    """Run the migration. The database must already be initialized."""
    async with get_session() as db:
        result = await db.execute(
            text(
                "SELECT id, team_id, autonomous FROM agents WHERE autonomous IS NOT NULL"
            )
        )
        agent_rows = [(r[0], r[1], r[2]) for r in result.all()]

        rows, stats = build_task_rows(agent_rows)

        # executemany: one round trip for all rows (ON CONFLICT keeps it idempotent).
        if rows:
            await db.execute(_INSERT, rows)

        await db.commit()

    logger.info(
        "Autonomous migration done: %d migrated, %d skipped (no team), %d skipped (no cron)",
        stats["migrated"],
        stats["skipped_no_team"],
        stats["skipped_no_cron"],
    )


async def migrate_if_table_empty() -> bool:
    """Run the migration only when ``autonomous_tasks`` has no rows yet.

    Called by the autonomous service at startup. The guard is row presence by
    design: once any task exists (migrated or newly created), boots skip the
    legacy scan. Caveat: if every task is deleted while the legacy
    ``agents.autonomous`` column still exists, the next service start
    re-imports the legacy tasks — accepted for the short window until the
    column and this script are removed. Returns True when the migration ran.
    """
    async with get_session() as db:
        existing = await db.execute(text("SELECT id FROM autonomous_tasks LIMIT 1"))
        if existing.first() is not None:
            logger.info("autonomous_tasks already has data; skipping legacy migration")
            return False

    await migrate()
    return True


async def main():
    await init_db(**config.db)
    await migrate()


if __name__ == "__main__":
    asyncio.run(main())
