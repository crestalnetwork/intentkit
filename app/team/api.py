"""Team API server module.

Standalone FastAPI application for team-scoped endpoints.
"""

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from intentkit.clients.s3_setup import ensure_bucket_exists_and_public
from intentkit.config.config import config
from intentkit.config.db import get_session, init_db
from intentkit.config.redis import init_redis
from intentkit.core.api import core_router
from intentkit.models.team import TeamMemberTable, TeamRole, TeamTable
from intentkit.models.user import UserTable
from intentkit.utils.alert import cleanup_alert
from intentkit.utils.error import (
    IntentKitAPIError,
    http_exception_handler,
    intentkit_api_error_handler,
    intentkit_other_error_handler,
    request_validation_exception_handler,
)

from app.common.health import health_router
from app.common.metadata import metadata_router
from app.team import (
    team_agent_router,
    team_autonomous_router,
    team_chat_router,
    team_content_router,
    team_lead_router,
    team_management_router,
    team_public_router,
    team_usage_router,
    team_user_router,
    team_wechat_router,
)

logger = logging.getLogger(__name__)

if config.sentry_dsn:
    _ = sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="team-api",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    """Manage application lifecycle."""
    await init_db(**config.db)

    _ = await init_redis(
        host=config.redis_host,
        port=config.redis_port,
        db=config.redis_db,
        password=config.redis_password,
        ssl=config.redis_ssl,
    )

    ensure_bucket_exists_and_public()

    await ensure_system_user_and_team()

    # Sync public agents from YAML files
    from intentkit.core.public_agents import (
        ensure_public_agent_prerequisites,
        sync_public_agents,
    )

    await ensure_public_agent_prerequisites()
    await sync_public_agents()

    logger.info("Team API server start")
    yield
    cleanup_alert()
    logger.info("Cleaning up and shutdown...")


app = FastAPI(
    lifespan=lifespan,
    title="IntentKit Team API",
    summary="IntentKit Team API Documentation",
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

_ = app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_ = app.include_router(health_router)
_ = app.include_router(core_router)
_ = app.include_router(metadata_router)
_ = app.include_router(team_agent_router)
_ = app.include_router(team_autonomous_router)
_ = app.include_router(team_chat_router)
_ = app.include_router(team_content_router)
_ = app.include_router(team_lead_router)
_ = app.include_router(team_management_router)
_ = app.include_router(team_usage_router)
_ = app.include_router(team_user_router)
_ = app.include_router(team_public_router)
_ = app.include_router(team_wechat_router)


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
