"""Run Alembic migrations programmatically at startup.

``init_db`` calls :func:`run_migrations` when ``auto_migrate`` is on, so every
deployment upgrades its own schema to head on boot — no manual ``alembic
upgrade`` step. The migration scripts ship inside the package
(``intentkit/migrations``), so pip-installed library users get the same
behavior for the intentkit-owned tables; application-owned tables belong to
the application's own Alembic chain (default ``alembic_version`` table — the
library chain uses ``alembic_version_intentkit``, so the two never collide).

First run on a pre-Alembic deployment (schema built by the retired
``safe_migrate``, no version table yet) is detected and the baseline revision
is stamped instead of executed; the following idempotent deltas then fill in
whatever is missing.

Concurrency: a Postgres advisory lock serializes concurrent starters
(several services / replicas booting after a deploy) around the whole
check-stamp-upgrade sequence, so exactly one runs it and the rest wake up to
find the schema already at head. A process-local thread lock additionally
guards Alembic's process-global runtime context.

Alembic runs synchronously (one-shot DDL gains nothing from async); call
:func:`run_migrations` via ``asyncio.to_thread`` from async code.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, create_engine, inspect, text

logger = logging.getLogger(__name__)

# Must match env.py's version_table. The sentinel is a core table from the
# baseline revision: present on every real deployment, absent on a fresh DB.
_VERSION_TABLE = "alembic_version_intentkit"
_SENTINEL_TABLE = "agents"

# App-wide advisory lock key for schema migrations; arbitrary but fixed.
_MIGRATION_LOCK_KEY = 411905021103

# Alembic's runtime context is process-global, so two in-process upgrade runs
# would race each other. Normal startups call run_migrations exactly once, but
# serialize defensively.
_process_lock = threading.Lock()


def find_script_location() -> Path | None:
    """Locate the migration scripts directory shipped inside the package.

    ``ALEMBIC_SCRIPT_LOCATION`` overrides discovery (e.g. a downstream project
    that vendors its own copy of the chain).
    """
    override = os.environ.get("ALEMBIC_SCRIPT_LOCATION")
    if override:
        path = Path(override)
        return path if (path / "env.py").exists() else None
    candidate = Path(__file__).resolve().parents[1] / "migrations"
    return candidate if (candidate / "env.py").exists() else None


def _stamp_baseline_if_pre_alembic(cfg: AlembicConfig, conn: Connection) -> None:
    """First run on an existing deployment: adopt the schema instead of
    rebuilding it.

    Pre-Alembic deployments have the full baseline schema (created by the
    retired ``safe_migrate``) but no version table. Executing the baseline
    would crash on the existing tables, so stamp it; the later revisions are
    idempotent and fill in exactly what such deployments are missing (e.g.
    indexes ``safe_migrate`` never created).
    """
    inspector = inspect(conn)
    if inspector.has_table(_VERSION_TABLE):
        return
    if not inspector.has_table(_SENTINEL_TABLE):
        return  # genuinely fresh database — run the whole chain
    bases = ScriptDirectory.from_config(cfg).get_bases()
    if len(bases) != 1:
        raise RuntimeError(f"Expected exactly one migration base, got {bases}")
    logger.info(
        "Existing schema without a version table — stamping baseline %s", bases[0]
    )
    command.stamp(cfg, bases[0])


def run_migrations(database_url: str) -> None:
    """Upgrade the intentkit-owned schema to head.

    Blocking — run in a thread from async code. ``database_url`` must use a
    sync driver (``postgresql+psycopg://``); it reaches ``env.py`` through the
    config attributes, overriding its own URL resolution.

    Propagates any migration failure — a deployment must not serve traffic on
    a schema it couldn't upgrade.
    """
    script_location = find_script_location()
    if script_location is None:
        raise RuntimeError(
            "Migration scripts not found; set ALEMBIC_SCRIPT_LOCATION or run "
            "with auto_migrate disabled and manage the schema yourself"
        )
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(script_location))
    cfg.attributes["database_url"] = database_url

    with _process_lock:
        engine = create_engine(database_url, future=True)
        try:
            with engine.connect() as conn:
                # Session-level lock held for this connection's lifetime and
                # released automatically on close — including when the process
                # dies mid-run. It spans the whole check-stamp-upgrade
                # sequence, so a concurrent starter can't stamp a database the
                # winner already upgraded. The commit closes the autobegun
                # transaction (the lock survives it); Alembic's own runs use
                # separate connections and manage their own transactions.
                conn.execute(
                    text("SELECT pg_advisory_lock(:key)"),
                    {"key": _MIGRATION_LOCK_KEY},
                )
                conn.commit()
                _stamp_baseline_if_pre_alembic(cfg, conn)
                logger.info("Running database migrations (alembic upgrade head)")
                command.upgrade(cfg, "head")
                logger.info("Database schema is at head")
        finally:
            engine.dispose()  # releases the advisory lock
