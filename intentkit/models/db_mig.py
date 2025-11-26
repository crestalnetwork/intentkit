"""Database migration utilities."""

import logging
from collections.abc import Callable

from sqlalchemy import Column, MetaData, inspect, text

from intentkit.models.base import Base

logger = logging.getLogger(__name__)


async def add_column_if_not_exists(
    conn, dialect, table_name: str, column: Column
) -> None:
    """Add a column to a table if it doesn't exist.

    Args:
        conn: SQLAlchemy conn
        table_name: Name of the table
        column: Column to add
    """

    # Use run_sync to perform inspection on the connection
    def _get_columns(connection):
        inspector = inspect(connection)
        return [c["name"] for c in inspector.get_columns(table_name)]

    columns = await conn.run_sync(_get_columns)

    if column.name not in columns:
        # Build column definition
        column_def = f"{column.name} {column.type.compile(dialect)}"

        # Add DEFAULT if specified
        if column.default is not None:
            if hasattr(column.default, "arg"):
                default_value = column.default.arg
                if not isinstance(default_value, Callable):
                    if isinstance(default_value, bool):
                        default_value = str(default_value).lower()
                    elif isinstance(default_value, str):
                        default_value = f"'{default_value}'"
                    elif isinstance(default_value, list | dict):
                        default_value = "'{}'"
                    column_def += f" DEFAULT {default_value}"

        # Execute ALTER TABLE
        await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def}"))
        logger.info(f"Added column {column.name} to table {table_name}")


async def update_table_schema(conn, dialect, model_cls) -> None:
    """Update table schema by adding missing columns from the model.

    Args:
        conn: SQLAlchemy conn
        dialect: SQLAlchemy dialect
        model_cls: SQLAlchemy model class to check for new columns
    """
    if not hasattr(model_cls, "__table__"):
        return

    table_name = model_cls.__tablename__
    for name, column in model_cls.__table__.columns.items():
        if name != "id":  # Skip primary key
            await add_column_if_not_exists(conn, dialect, table_name, column)


async def safe_migrate(engine) -> None:
    """Safely migrate all SQLAlchemy models by adding new columns.

    Args:
        engine: SQLAlchemy engine
    """
    logger.info("Starting database schema migration")
    dialect = engine.dialect

    async with engine.begin() as conn:
        try:
            # Create tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)

            # Get existing table metadata
            metadata = MetaData()
            await conn.run_sync(metadata.reflect)

            # Update schema for all model classes
            for mapper in Base.registry.mappers:
                model_cls = mapper.class_
                if hasattr(model_cls, "__tablename__"):
                    table_name = model_cls.__tablename__
                    if table_name in metadata.tables:
                        # We need a sync wrapper for the async update_table_schema
                        async def update_table_wrapper():
                            await update_table_schema(conn, dialect, model_cls)

                        await update_table_wrapper()

            # Migrate checkpoints tables
            await migrate_checkpoints_table(conn)
        except Exception as e:
            logger.error(f"Error updating database schema: {str(e)}")
            raise

    logger.info("Database schema updated successfully")


async def migrate_checkpoints_table(conn) -> None:
    """Migrate checkpoints tables to support langgraph 2.0."""
    tables = ["checkpoints", "checkpoint_blobs", "checkpoint_writes"]

    def _get_tables(connection):
        insp = inspect(connection)
        return insp.get_table_names()

    existing_tables = await conn.run_sync(_get_tables)

    for table in tables:
        if table not in existing_tables:
            continue

        # 1. Add checkpoint_ns column
        await conn.execute(
            text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS checkpoint_ns TEXT DEFAULT ''"
            )
        )

        # 2. Drop columns that ShallowPostgresSaver doesn't use
        if table == "checkpoints":
            # ShallowPostgresSaver doesn't use checkpoint_id or parent_checkpoint_id
            await conn.execute(
                text("ALTER TABLE checkpoints DROP COLUMN IF EXISTS checkpoint_id")
            )
            await conn.execute(
                text(
                    "ALTER TABLE checkpoints DROP COLUMN IF EXISTS parent_checkpoint_id"
                )
            )
        elif table == "checkpoint_blobs":
            # ShallowPostgresSaver doesn't use version column
            await conn.execute(
                text("ALTER TABLE checkpoint_blobs DROP COLUMN IF EXISTS version")
            )

        # 3. Update Primary Key
        def _check_pk(connection, table_name=table):
            insp = inspect(connection)
            return insp.get_pk_constraint(table_name)

        pk = await conn.run_sync(_check_pk)
        current_cols = set(pk.get("constrained_columns", []))

        # Expected columns depend on table
        expected_cols = set()
        pk_cols = ""
        if table == "checkpoints":
            expected_cols = {"thread_id", "checkpoint_ns"}
            pk_cols = "thread_id, checkpoint_ns"
        elif table == "checkpoint_blobs":
            expected_cols = {"thread_id", "checkpoint_ns", "channel"}
            pk_cols = "thread_id, checkpoint_ns, channel"
        elif table == "checkpoint_writes":
            expected_cols = {
                "thread_id",
                "checkpoint_ns",
                "checkpoint_id",
                "task_id",
                "idx",
            }
            pk_cols = "thread_id, checkpoint_ns, checkpoint_id, task_id, idx"

        if current_cols != expected_cols:
            logger.info(f"Migrating {table} PK from {current_cols} to {expected_cols}")

            # If migrating checkpoints to (thread_id, checkpoint_ns), we need to handle duplicates
            if table == "checkpoints" and expected_cols == {
                "thread_id",
                "checkpoint_ns",
            }:
                # Keep only the latest checkpoint for each (thread_id, checkpoint_ns) based on checkpoint_id (time-ordered)
                await conn.execute(
                    text("""
                    DELETE FROM checkpoints
                    WHERE (thread_id, checkpoint_ns, checkpoint_id) NOT IN (
                        SELECT thread_id, checkpoint_ns, MAX(checkpoint_id)
                        FROM checkpoints
                        GROUP BY thread_id, checkpoint_ns
                    )
                """)
                )

            # If migrating checkpoint_blobs to (thread_id, checkpoint_ns, channel), we need to handle duplicates
            elif table == "checkpoint_blobs" and expected_cols == {
                "thread_id",
                "checkpoint_ns",
                "channel",
            }:
                # Keep only blobs that are referenced by the remaining checkpoints
                # The relationship is: checkpoints.checkpoint -> 'channel_versions' ->> blob.channel = blob.version
                await conn.execute(
                    text("""
                    DELETE FROM checkpoint_blobs cb
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM checkpoints cp
                        WHERE cp.thread_id = cb.thread_id
                          AND cp.checkpoint_ns = cb.checkpoint_ns
                          AND (cp.checkpoint -> 'channel_versions' ->> cb.channel) = cb.version
                    )
                """)
                )

            if pk.get("name"):
                await conn.execute(
                    text(f"ALTER TABLE {table} DROP CONSTRAINT {pk['name']}")
                )

            await conn.execute(text(f"ALTER TABLE {table} ADD PRIMARY KEY ({pk_cols})"))
