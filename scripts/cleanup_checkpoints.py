#!/usr/bin/env python3
"""
LangGraph Checkpoint Cleanup Script

This script cleans up old checkpoints, writes, and blobs, keeping only the latest one for each thread.
It processes threads in batches to handle large datasets efficiently and supports resuming.

Usage:
    python scripts/cleanup_checkpoints.py [--batch-size 100] [--reset-progress]
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from intentkit.config.config import config
from intentkit.models.db import get_session, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROGRESS_FILE = Path(".cleanup_progress")


class CheckpointCleaner:
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.total_threads_processed = 0
        self.total_checkpoints_deleted = 0
        self.total_writes_deleted = 0
        self.total_blobs_deleted = 0

    def get_last_processed_thread_id(self) -> str:
        if PROGRESS_FILE.exists():
            return PROGRESS_FILE.read_text().strip()
        return ""

    def save_progress(self, thread_id: str):
        PROGRESS_FILE.write_text(thread_id)

    def reset_progress(self):
        if PROGRESS_FILE.exists():
            os.remove(PROGRESS_FILE)
        logger.info("Progress reset.")

    async def get_thread_batch(
        self, session: AsyncSession, last_thread_id: str
    ) -> list[str]:
        stmt = text("""
            SELECT DISTINCT thread_id 
            FROM checkpoints 
            WHERE thread_id > :last_id 
            ORDER BY thread_id 
            LIMIT :batch_size
        """)
        result = await session.execute(
            stmt, {"last_id": last_thread_id, "batch_size": self.batch_size}
        )
        return [row[0] for row in result.fetchall()]

    async def cleanup_batch(self, session: AsyncSession, thread_ids: list[str]):
        if not thread_ids:
            return

        # 1. Delete old checkpoints
        cleanup_checkpoints_sql = text("""
            DELETE FROM checkpoints
            WHERE thread_id = ANY(:thread_ids)
              AND (thread_id, checkpoint_ns, checkpoint_id) NOT IN (
                SELECT DISTINCT ON (thread_id, checkpoint_ns)
                    thread_id, checkpoint_ns, checkpoint_id
                FROM checkpoints
                WHERE thread_id = ANY(:thread_ids)
                ORDER BY thread_id, checkpoint_ns, checkpoint_id DESC
            )
        """)
        result = await session.execute(
            cleanup_checkpoints_sql, {"thread_ids": thread_ids}
        )
        self.total_checkpoints_deleted += result.rowcount

        # 2. Delete orphaned writes
        cleanup_writes_sql = text("""
            DELETE FROM checkpoint_writes
            WHERE thread_id = ANY(:thread_ids)
              AND (thread_id, checkpoint_ns, checkpoint_id) NOT IN (
                SELECT thread_id, checkpoint_ns, checkpoint_id
                FROM checkpoints
                WHERE thread_id = ANY(:thread_ids)
            )
        """)
        result = await session.execute(cleanup_writes_sql, {"thread_ids": thread_ids})
        self.total_writes_deleted += result.rowcount

        # 3. Delete orphaned blobs
        # Optimized using NOT EXISTS and CTE
        cleanup_blobs_sql = text("""
            WITH active_versions AS (
                SELECT DISTINCT 
                    thread_id, 
                    checkpoint_ns, 
                    key as channel, 
                    value as version
                FROM checkpoints, 
                     jsonb_each_text(checkpoint -> 'channel_versions')
                WHERE thread_id = ANY(:thread_ids)
            )
            DELETE FROM checkpoint_blobs cb
            WHERE cb.thread_id = ANY(:thread_ids)
              AND NOT EXISTS (
                SELECT 1 
                FROM active_versions av
                WHERE av.thread_id = cb.thread_id
                  AND av.checkpoint_ns = cb.checkpoint_ns
                  AND av.channel = cb.channel
                  AND av.version = cb.version
            )
        """)
        result = await session.execute(cleanup_blobs_sql, {"thread_ids": thread_ids})
        self.total_blobs_deleted += result.rowcount

    async def run(self):
        await init_db(**config.db)

        last_thread_id = self.get_last_processed_thread_id()
        logger.info(f"Resuming from thread_id: '{last_thread_id}'")

        async with get_session() as session:
            while True:
                thread_ids = await self.get_thread_batch(session, last_thread_id)
                if not thread_ids:
                    logger.info("No more threads to process.")
                    break

                logger.info(
                    f"Processing batch of {len(thread_ids)} threads starting from {thread_ids[0]}"
                )

                try:
                    await self.cleanup_batch(session, thread_ids)
                    await session.commit()

                    last_thread_id = thread_ids[-1]
                    self.save_progress(last_thread_id)
                    self.total_threads_processed += len(thread_ids)

                    logger.info(
                        f"Batch completed. Total processed: {self.total_threads_processed} threads. "
                        f"Deleted: {self.total_checkpoints_deleted} checkpoints, "
                        f"{self.total_writes_deleted} writes, {self.total_blobs_deleted} blobs."
                    )
                except Exception as e:
                    logger.error(f"Error processing batch: {e}")
                    await session.rollback()
                    raise e

        logger.info("Cleanup completed successfully.")
        # Clean up progress file on successful completion
        if PROGRESS_FILE.exists():
            os.remove(PROGRESS_FILE)


async def main():
    parser = argparse.ArgumentParser(description="Clean up old LangGraph checkpoints.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of threads to process per batch",
    )
    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Reset progress and start from beginning",
    )
    args = parser.parse_args()

    cleaner = CheckpointCleaner(batch_size=args.batch_size)

    if args.reset_progress:
        cleaner.reset_progress()

    await cleaner.run()


if __name__ == "__main__":
    asyncio.run(main())
