import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from intentkit.core.system_skills.create_activity import CreateActivitySkill
from intentkit.core.system_skills.create_post import CreatePostSkill


# Mock runtime context
class MockContext:
    def __init__(self, agent_id):
        self.agent_id = agent_id


async def verify_activity_creation():
    print("Verifying AgentActivity creation...")
    # diverse-shrew-46 is a known agent ID from previous sessions or we can fetch one
    # But better to just mock one or use an existing one.
    # Let's try to fetch an existing agent first.
    from sqlalchemy import select

    from intentkit.models.agent import AgentTable
    from intentkit.models.db import get_session

    async with get_session() as session:
        stmt = select(AgentTable).limit(1)
        result = await session.execute(stmt)
        agent_table = result.scalar_one_or_none()

    if not agent_table:
        print("No agent found in DB. Skipping verification.")
        return

    agent_id = agent_table.id
    print(f"Using agent: {agent_id}, Name: {agent_table.name}")

    # Mock context setup for Skill execution if needed, but we can call creation functions directly
    # OR we can mock the runtime context for skills.
    # Let's verify the logic in the SKILLs since that's what we changed.

    # To test skills, we need to mock get_runtime.
    # Since patching might be complex in this script without pytest,
    # let's try to instantiate imports carefully or verify the logic by "dry running" the code paths
    # via copying the logic or using a test harness if available.

    # Actually, simpler: create an activity via create_agent_activity with explicit fields matched from what the skill WOULD do.
    # Wait, the meaningful change is IN the skill/entrypoint code.
    # So I must execute the SKILL code.

    # Let's try to patch get_runtime
    from unittest.mock import patch

    with patch(
        "intentkit.core.system_skills.create_activity.get_runtime"
    ) as mock_get_runtime:
        mock_get_runtime.return_value.context = MockContext(agent_id)

        skill = CreateActivitySkill()
        # We need to run _arun. BaseTool hides it.
        # But we can call input schema manually?
        # BaseTool call method handles it.

        try:
            res = await skill._arun(text="Test Activity for Redundant Fields")
            print(f"Activity creation result: {res}")

            # Extract ID and check DB
            activity_id = res.split("ID: ")[1].strip()

            from intentkit.core.agent_activity import get_agent_activity

            activity = await get_agent_activity(activity_id)

            print(f"Activity Agent Name: {activity.agent_name}")
            print(f"Activity Agent Picture: {activity.agent_picture}")

            if activity.agent_name == agent_table.name:
                print("SUCCESS: agent_name populated in Activity")
            else:
                print(
                    f"FAILURE: agent_name mismatch. Expected {agent_table.name}, got {activity.agent_name}"
                )

            if activity.agent_picture == agent_table.picture:
                print("SUCCESS: agent_picture populated in Activity")
            else:
                print(
                    f"FAILURE: agent_picture mismatch. Expected {agent_table.picture}, got {activity.agent_picture}"
                )

        except Exception as e:
            print(f"Error testing CreateActivitySkill: {e}")
            import traceback

            traceback.print_exc()


async def verify_post_creation():
    print("\nVerifying AgentPost creation...")
    from sqlalchemy import select

    from intentkit.models.agent import AgentTable
    from intentkit.models.db import get_session

    async with get_session() as session:
        stmt = select(AgentTable).limit(1)
        result = await session.execute(stmt)
        agent_table = result.scalar_one_or_none()

    if not agent_table:
        return

    agent_id = agent_table.id

    from unittest.mock import patch

    with patch(
        "intentkit.core.system_skills.create_post.get_runtime"
    ) as mock_get_runtime:
        mock_get_runtime.return_value.context = MockContext(agent_id)

        skill = CreatePostSkill()

        try:
            import time

            slug = f"test-post-{int(time.time())}"
            res = await skill._arun(
                title="Test Post for Redundant Fields",
                markdown="Content...",
                slug=slug,
                excerpt="Excerpt...",
                tags=["test"],
            )
            print(f"Post creation result: {res}")

            post_id = res.split("ID: ")[1].strip()

            # We assume get_agent_post exists or similar
            # If not, we query DB directly
            async with get_session() as session:
                from intentkit.models.agent_post import AgentPostTable

                stmt = select(AgentPostTable).where(AgentPostTable.id == post_id)
                r = await session.execute(stmt)
                post = r.scalar_one()

                print(f"Post Agent Name: {post.agent_name}")
                print(f"Post Agent Picture: {post.agent_picture}")

                if post.agent_picture == agent_table.picture:
                    print("SUCCESS: agent_picture populated in Post")
                else:
                    print(
                        f"FAILURE: agent_picture mismatch. Expected {agent_table.picture}, got {post.agent_picture}"
                    )

                # Verify associated activity
                from intentkit.models.agent_activity import AgentActivityTable

                stmt2 = select(AgentActivityTable).where(
                    AgentActivityTable.post_id == post_id
                )
                r2 = await session.execute(stmt2)
                activity = r2.scalar_one()

                print(f"Associated Activity Agent Name: {activity.agent_name}")
                print(f"Associated Activity Agent Picture: {activity.agent_picture}")

                if activity.agent_picture == agent_table.picture:
                    print("SUCCESS: agent_picture populated in Associated Activity")
                else:
                    print("FAILURE: agent_picture mismatch in Activity")

        except Exception as e:
            print(f"Error testing CreatePostSkill: {e}")
            import traceback

            traceback.print_exc()


async def main():
    from dotenv import load_dotenv

    load_dotenv()  # Load env vars for DB connection

    from intentkit.config.config import Config
    from intentkit.models.db import init_db

    # Load config from env
    # Assuming Config() loads from env automatically or we just use os.environ
    # Looking at config.py (not shown but assumed typical pattern), let's rely on os.environ if Config is Pydantic Settings
    # Or cleaner: instantiate Config().

    cfg = Config()

    # Config object has db dict
    db_config = cfg.db

    await init_db(
        host=db_config.get("host"),
        username=db_config.get("username"),
        password=db_config.get("password"),
        dbname=db_config.get("dbname"),
        port=db_config.get("port"),
        auto_migrate=True,
    )

    await verify_activity_creation()
    await verify_post_creation()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
