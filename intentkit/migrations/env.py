"""Alembic migration environment.

The application runs on an async engine (asyncpg), but migrations run
synchronously here via ``postgresql+psycopg://`` — there is no benefit to async
for one-shot DDL, and a sync engine keeps this file simple.

Connection comes from ``config.db`` (the same DB the app uses) unless
``ALEMBIC_DATABASE_URL`` is set, which overrides it (used to point autogenerate
/ verification at a throwaway database without touching the dev DB).

``target_metadata`` is the shared ``Base.metadata``; every model module is
imported below so all tables register on it. Tables the app does NOT own (the
langgraph checkpoint tables, created by ``AsyncPostgresSaver.setup()``, and
Alembic's own ``alembic_version``) are filtered out of autogenerate so it never
proposes to drop them.
"""

import importlib
import os
import pkgutil
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import create_engine

import intentkit.models as _models_pkg
from intentkit.config.base import Base
from intentkit.config.config import config as app_config

# Import every model module so its tables attach to Base.metadata. The models
# package has no eager imports of its own, so discover and import submodules.
for _mod in pkgutil.walk_packages(_models_pkg.__path__, prefix="intentkit.models."):
    importlib.import_module(_mod.name)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# JSONB expression indexes that live in migrations, not in the models (SQLAlchemy
# can't round-trip a functional index through autogenerate reliably). Excluded
# from comparison so ``alembic check`` doesn't perpetually propose to drop them.
_MIGRATION_MANAGED_INDEXES = {
    "ix_team_channels_slack_workspace",
    "ix_team_channels_lark_tenant",
}


def _database_url() -> str:
    """Sync (psycopg) URL for migrations.

    Precedence: the ``database_url`` config attribute (set by the startup
    runner, ``intentkit.config.migration``), then ``ALEMBIC_DATABASE_URL``
    (used to point autogenerate / verification at a throwaway database), then
    the app's own DB config (CLI usage from a dev checkout).
    """
    from_runner = config.attributes.get("database_url")
    if from_runner:
        return from_runner
    override = os.environ.get("ALEMBIC_DATABASE_URL")
    if override:
        return override
    db = app_config.db
    user = db.get("username") or ""
    password = db.get("password") or ""
    host = db.get("host")
    port = db.get("port") or "5432"
    name = db.get("dbname")
    auth = f"{user}:{quote_plus(password)}@" if (user or password) else ""
    return f"postgresql+psycopg://{auth}{host}:{port}/{name}"


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Keep autogenerate scoped to tables the app owns.

    Reflected tables that aren't in Base.metadata (langgraph checkpoints,
    alembic_version) must be ignored so autogenerate never tries to drop them.
    """
    if type_ == "table" and name not in target_metadata.tables:
        return False
    return not (type_ == "index" and name in _MIGRATION_MANAGED_INDEXES)


# Library-owned version table. Downstream applications build their own models
# (and their own Alembic chain, default table "alembic_version") on top of the
# intentkit library; the dedicated name keeps the two chains fully independent
# in one database. Concurrency control (advisory lock) lives in the startup
# runner, intentkit/config/migration.py, which wraps stamp + upgrade in one
# critical section.
_VERSION_TABLE = "alembic_version_intentkit"


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
        version_table=_VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), future=True)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_object=include_object,
                compare_type=True,
                version_table=_VERSION_TABLE,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        # Also on failure — connections must not outlive the run.
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
