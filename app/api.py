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
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.admin import (
    admin_router,
    admin_router_readonly,
    credit_router,
    credit_router_readonly,
    health_router,
    metadata_router_readonly,
    schema_router_readonly,
    user_router,
    user_router_readonly,
)
from app.config.config import config
from app.core.api import core_router
from app.entrypoints.web import chat_router, chat_router_readonly
from app.services.twitter.oauth2 import router as twitter_oauth2_router
from app.services.twitter.oauth2_callback import router as twitter_callback_router
from models.db import init_db
from models.redis import init_redis
from utils.error import (
    IntentKitAPIError,
    http_exception_handler,
    intentkit_api_error_handler,
    intentkit_other_error_handler,
    request_validation_exception_handler,
)

# init logger
logger = logging.getLogger(__name__)

if config.sentry_dsn:
    sentry_sdk.init(
        dsn=config.sentry_dsn,
        sample_rate=config.sentry_sample_rate,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
        environment=config.env,
        release=config.release,
        server_name="intent-api",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    # Initialize Redis if configured
    if config.redis_host:
        await init_redis(
            host=config.redis_host,
            port=config.redis_port,
        )

    logger.info("API server start")
    yield
    # Clean up will run after the API server shutdown
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


app.exception_handler(IntentKitAPIError)(intentkit_api_error_handler)
app.exception_handler(RequestValidationError)(request_validation_exception_handler)
app.exception_handler(StarletteHTTPException)(http_exception_handler)
app.exception_handler(Exception)(intentkit_other_error_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(chat_router)
app.include_router(chat_router_readonly)
app.include_router(admin_router)
app.include_router(admin_router_readonly)
app.include_router(metadata_router_readonly)
app.include_router(credit_router)
app.include_router(credit_router_readonly)
app.include_router(schema_router_readonly)
app.include_router(user_router)
app.include_router(user_router_readonly)
app.include_router(core_router)
app.include_router(twitter_callback_router)
app.include_router(twitter_oauth2_router)
app.include_router(health_router)
