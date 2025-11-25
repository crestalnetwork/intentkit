import asyncio
import logging

from sqlalchemy import text

from intentkit.config.config import config
from intentkit.models.db import get_session, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def inspect():
    print(f"DB Host: {config.db.get('host')}")
    print(f"DB Name: {config.db.get('dbname')}")
    print(f"DB Port: {config.db.get('port')}")

    await init_db(**config.db)
    async with get_session() as session:
        # 1. Total counts
        result = await session.execute(
            text("SELECT count(DISTINCT thread_id), count(*) FROM checkpoints")
        )
        threads, total = result.fetchone()
        print(f"Total Threads: {threads}")
        print(f"Total Checkpoints: {total}")

        result = await session.execute(text("SELECT count(*) FROM checkpoint_writes"))
        writes_count = result.scalar()
        print(f"Total Writes: {writes_count}")

        result = await session.execute(text("SELECT count(*) FROM checkpoint_blobs"))
        blobs_count = result.scalar()
        print(f"Total Blobs: {blobs_count}")

        if threads > 0:
            print(f"Avg Checkpoints per Thread: {total / threads:.2f}")

        # 2. Top threads by checkpoint count
        print("\nTop 5 Threads by Checkpoint Count:")
        stmt = text("""
            SELECT thread_id, count(*) as c 
            FROM checkpoints 
            GROUP BY thread_id 
            ORDER BY c DESC 
            LIMIT 5
        """)
        result = await session.execute(stmt)
        top_threads = result.fetchall()
        for row in top_threads:
            print(f"Thread: {row[0]}, Count: {row[1]}")

        # 3. Inspect namespaces for the top thread
        if top_threads:
            top_thread_id = top_threads[0][0]
            print(f"\nNamespace distribution for thread {top_thread_id}:")
            stmt = text("""
                SELECT checkpoint_ns, count(*) 
                FROM checkpoints 
                WHERE thread_id = :tid 
                GROUP BY checkpoint_ns
            """)
            result = await session.execute(stmt, {"tid": top_thread_id})
            for row in result.fetchall():
                print(f"NS: '{row[0]}', Count: {row[1]}")

            # 4. Sample checkpoint IDs
            print(f"\nSample Checkpoint IDs for thread {top_thread_id} (limit 5):")
            stmt = text("""
                SELECT checkpoint_id, checkpoint_ns 
                FROM checkpoints 
                WHERE thread_id = :tid 
                ORDER BY checkpoint_id DESC 
                LIMIT 5
            """)
            result = await session.execute(stmt, {"tid": top_thread_id})
            for row in result.fetchall():
                print(f"ID: {row[0]}, NS: '{row[1]}'")


if __name__ == "__main__":
    asyncio.run(inspect())
