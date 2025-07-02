"""Database migration utilities."""

import logging
from typing import Callable

from intentkit.models.base import Base
from sqlalchemy import Column, MetaData, inspect, text

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
                    elif isinstance(default_value, (list, dict)):
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
        except Exception as e:
            logger.error(f"Error updating database schema: {str(e)}")
            raise

    logger.info("Database schema updated successfully")
