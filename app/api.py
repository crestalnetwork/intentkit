"""API server module.

This module initializes and configures the FastAPI application,
including routers, middleware, and startup/shutdown events.

The API server provides endpoints for agent execution and management.
"""

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from intentkit.clients.s3_setup import ensure_bucket_exists_and_public
from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.config.redis import init_redis
from intentkit.core.api import core_router
from intentkit.models.agent import AgentTable
from intentkit.models.team import TeamMemberTable, TeamRole, TeamTable
from intentkit.models.team_channel import (  # noqa: F401 (register with Base.metadata for auto-migration)
    TeamChannelDataTable,
    TeamChannelTable,
)
from intentkit.models.user import UserTable
from intentkit.utils.alert import cleanup_alert
from intentkit.utils.error import (
    IntentKitAPIError,
    http_exception_handler,
    intentkit_api_error_handler,
    intentkit_other_error_handler,
    request_validation_exception_handler,
)

from app.local import (
    agent_router,
    autonomous_router,
    chat_router,
    content_router,
    health_router,
    lead_router,
    metadata_router,
    schema_router,
)
from app.services.twitter.oauth2 import twitter_oauth2_router
from app.services.twitter.oauth2_callback import twitter_callback_router

logger = logging.getLogger(__name__)

if config.sentry_dsn:
    _ = sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        # traces_sample_rate=config.sentry_traces_sample_rate,
        # profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-api",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    """Manage application lifecycle.

    This context manager:
    1. Initializes database connection
    2. Performs any necessary startup tasks
    3. Handles graceful shutdown

    Args:
        app: FastAPI application instance
    """
    # Initialize database
    await init_db(**config.db)

    # Initialize Redis
    _ = await init_redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        password=config.redis_password,
        ssl=config.redis_ssl,
    )

    # Initialize S3 bucket (Create & Set Public Policy if needed)
    # This is synchronous but fast enough for startup
    ensure_bucket_exists_and_public()

    await ensure_system_user_and_team()

    # Create example agent if no agents exist
    await create_example_agent()

    logger.info("API server start")
    yield
    # Clean up will run after the API server shutdown
    cleanup_alert()
    logger.info("Cleaning up and shutdown...")


app = FastAPI(
    lifespan=lifespan,
    title="IntentKit API",
    summary="IntentKit API Documentation",
    version=config.release,
    contact={
        "name": "IntentKit Team",
        "url": "https://github.com/crestalnetwork/intentkit",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

_ = app.exception_handler(IntentKitAPIError)(intentkit_api_error_handler)
_ = app.exception_handler(RequestValidationError)(request_validation_exception_handler)
_ = app.exception_handler(StarletteHTTPException)(http_exception_handler)
_ = app.exception_handler(Exception)(intentkit_other_error_handler)

# Add CORS middleware
# NOTE: Permissive CORS is intentional — the API is designed to be
# called from any origin (third-party frontends, embedded widgets, etc.).
_ = app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# NOTE: Local/core routes are intentionally unauthenticated.
# They are designed for local development and debugging only.
# In production, these should not be exposed to the public internet.
_ = app.include_router(agent_router)
_ = app.include_router(autonomous_router)
_ = app.include_router(chat_router)
_ = app.include_router(lead_router)
_ = app.include_router(content_router)
_ = app.include_router(metadata_router)
_ = app.include_router(schema_router)
_ = app.include_router(core_router)
_ = app.include_router(twitter_callback_router, include_in_schema=False)
_ = app.include_router(twitter_oauth2_router)
_ = app.include_router(health_router)


async def create_example_agent() -> None:
    """Create an example agent if no agents exist in the database.

    Creates an agent with ID 'example' and basic configuration if the agents table is empty.
    """
    try:
        async with get_session() as session:
            # Check if any agents exist - more efficient count query
            result = await session.execute(
                select(select(AgentTable.id).limit(1).exists().label("exists"))
            )
            if result.scalar():
                logger.debug("Example agent not created: agents already exist")
                return  # Agents exist, nothing to do

            # Create example agent
            example_agent = AgentTable(
                id="example",
                name="Example",
                slug="example",
                owner="system",
                team_id="system",
                purpose="IntentKit example agent",
                search_internet=True,
                enable_activity=True,
                enable_post=True,
                enable_long_term_memory=True,
                skills={
                    "ui": {
                        "states": {
                            "ui_ask_user": "public",
                            "ui_show_card": "public",
                        },
                        "enabled": True,
                    },
                },
            )

            session.add(example_agent)
            await session.commit()
            logger.info("Created example agent with ID 'example'")
    except Exception as e:
        logger.error("Failed to create example agent: %s", e)
        # Don't re-raise the exception to avoid blocking server startup


async def ensure_system_user_and_team() -> None:
    try:
        async with get_session() as session:
            system_user = await session.get(UserTable, "system")
            if not system_user:
                session.add(UserTable(id="system"))

            system_team = await session.get(TeamTable, "system")
            if not system_team:
                session.add(TeamTable(id="system", name="system"))

            system_member = await session.get(
                TeamMemberTable, {"team_id": "system", "user_id": "system"}
            )
            if not system_member:
                session.add(
                    TeamMemberTable(
                        team_id="system",
                        user_id="system",
                        role=TeamRole.OWNER,
                    )
                )

            await session.commit()
    except Exception as e:
        logger.error("Failed to create system user/team: %s", e)
