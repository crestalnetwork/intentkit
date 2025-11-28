import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from intentkit.config.config import config
from intentkit.models.db import get_session, init_db

logger = logging.getLogger(__name__)


async def cleanup_checkpoints(days: int = 90, dry_run: bool = False) -> int:
    """
    Cleanup checkpoints older than the specified number of days.

    Args:
        days: Number of days to keep history for.
        dry_run: If True, only count threads to be deleted without deleting.

    Returns:
        int: Number of threads deleted (or found, if dry_run is True).
    """
    # Ensure DB is initialized (idempotent)
    await init_db(**config.db)

    # Use UTC for consistency with LangGraph timestamps
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    logger.info(
        f"Cleaning up threads older than {days} days (before {cutoff_date.isoformat()})"
    )

    # 1. Identify threads to delete
    count_query = text("""
        SELECT count(DISTINCT thread_id)
        FROM checkpoints
        WHERE (checkpoint ->> 'ts')::timestamptz < :cutoff
    """)

    async with get_session() as session:
        result = await session.execute(count_query, {"cutoff": cutoff_date})
        thread_count = result.scalar()

    logger.info(f"Found {thread_count} threads to delete.")

    if thread_count == 0:
        return 0

    if dry_run:
        logger.info("Dry run enabled. No changes made.")
        return thread_count

    # 2. Perform deletion
    logger.info("Deleting...")
    async with get_session() as session:
        async with session.begin():
            delete_stmt = text("""
                WITH old_threads AS (
                    SELECT thread_id, checkpoint_ns
                    FROM checkpoints
                    WHERE (checkpoint ->> 'ts')::timestamptz < :cutoff
                ),
                deleted_writes AS (
                    DELETE FROM checkpoint_writes cw
                    USING old_threads ot
                    WHERE cw.thread_id = ot.thread_id AND cw.checkpoint_ns = ot.checkpoint_ns
                ),
                deleted_blobs AS (
                    DELETE FROM checkpoint_blobs cb
                    USING old_threads ot
                    WHERE cb.thread_id = ot.thread_id AND cb.checkpoint_ns = ot.checkpoint_ns
                )
                DELETE FROM checkpoints cp
                USING old_threads ot
                WHERE cp.thread_id = ot.thread_id AND cp.checkpoint_ns = ot.checkpoint_ns
            """)

            await session.execute(delete_stmt, {"cutoff": cutoff_date})
            logger.info("Deletion completed.")

    return thread_count
