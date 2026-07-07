"""Tests for the startup Alembic runner (intentkit/config/migration.py).

The fresh-database upgrade test doubles as the CI guard that the migration
chain (baseline -> deltas) applies cleanly, so a broken revision can never
ship: every deployment now runs exactly this path on boot.
"""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

import psycopg
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect, text

from intentkit.config.migration import find_script_location, run_migrations

MIGRATION_DB = "alembic_upgrade_smoke"


def test_script_location_found_in_checkout():
    location = find_script_location()
    assert location is not None
    assert (location / "env.py").exists()


def test_missing_script_location_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("ALEMBIC_SCRIPT_LOCATION", str(tmp_path / "nowhere"))
    assert find_script_location() is None
    with pytest.raises(RuntimeError, match="ALEMBIC_SCRIPT_LOCATION"):
        run_migrations("postgresql+psycopg://localhost/unused")


@pytest.fixture
def fresh_db_url(postgresql_server) -> str:
    """A dedicated empty database on the shared test Postgres server.

    The suite's main ``test`` database accumulates ad-hoc tables from other
    tests, which would collide with the (non-idempotent) baseline revision.
    """
    server_url = postgresql_server.url()
    with psycopg.connect(server_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            _ = cur.execute(f"DROP DATABASE IF EXISTS {MIGRATION_DB}")
            _ = cur.execute(f"CREATE DATABASE {MIGRATION_DB}")
    base = server_url.rsplit("/", 1)[0]
    return f"{base}/{MIGRATION_DB}".replace("postgresql://", "postgresql+psycopg://", 1)


def test_concurrent_starters_serialize(fresh_db_url):
    """Several services booting at once (post-deploy) must not collide: the
    Postgres advisory lock in env.py serializes them, followers find head.

    Real processes, like real service starts — Alembic's runtime context is
    process-global, so in-process concurrency is not the deployment shape
    (run_migrations additionally guards that with a thread lock).
    """
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=3, mp_context=ctx) as pool:
        futures = [pool.submit(run_migrations, fresh_db_url) for _ in range(3)]
        for future in futures:
            future.result(timeout=120)  # raises if any runner failed

    engine = create_engine(fresh_db_url)
    try:
        assert "team_links" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_pre_alembic_deployment_is_adopted(fresh_db_url):
    """First run on an existing deployment (schema built by the retired
    safe_migrate, no version table): the baseline must be stamped, not
    executed — executing it would crash on the existing tables."""
    # Build the "existing schema" state, then erase Alembic's memory of it.
    run_migrations(fresh_db_url)
    engine = create_engine(fresh_db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE alembic_version_intentkit"))

        # Must adopt the schema (stamp + idempotent deltas), not crash.
        run_migrations(fresh_db_url)

        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version_intentkit")
            ).scalar()
        assert version is not None
    finally:
        engine.dispose()


def test_upgrade_head_on_fresh_database(fresh_db_url):
    run_migrations(fresh_db_url)
    # Running again must be a no-op (every boot calls this).
    run_migrations(fresh_db_url)

    engine = create_engine(fresh_db_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        # Baseline schema plus the newest delta both applied
        assert "agents" in tables
        assert "teams" in tables
        assert "team_links" in tables
        index_names = {idx["name"] for idx in inspector.get_indexes("team_links")}
        assert "ix_team_links_connected_account" in index_names
        link_columns = {col["name"] for col in inspector.get_columns("team_links")}
        assert {"level", "user_id"} <= link_columns

        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version_intentkit")
            ).scalar()
        assert version is not None
    finally:
        engine.dispose()


def test_team_link_levels_normalizes_existing_rows(fresh_db_url):
    """Rows created before the levels delta converge on the whitelist rules:
    user-level apps bind to their initiator, unrecoverable rows are dropped,
    team-level apps stay untouched."""
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(find_script_location()))
    cfg.attributes["database_url"] = fresh_db_url
    # Build the schema as it was just before the levels delta.
    command.upgrade(cfg, "f6a1d8c3b7e2")

    engine = create_engine(fresh_db_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO team_links "
                    "(id, team_id, app, connected_account_id, status, created_by) "
                    "VALUES "
                    "('l1', 't1', 'gmail', 'ca_1', 'active', 'u1'), "
                    "('l2', 't1', 'twitter', 'ca_2', 'active', 'u2'), "
                    "('l3', 't1', 'gmail', 'ca_3', 'active', '')"
                )
            )

        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            rows = {
                row.id: row
                for row in conn.execute(
                    text("SELECT id, level, user_id FROM team_links")
                )
            }
        # gmail is user-level now: owned by whoever initiated it
        assert (rows["l1"].level, rows["l1"].user_id) == ("user", "u1")
        # twitter stays a shared team-level link
        assert (rows["l2"].level, rows["l2"].user_id) == ("team", None)
        # a user-level-app row with no recoverable owner is dropped
        assert "l3" not in rows
    finally:
        engine.dispose()
