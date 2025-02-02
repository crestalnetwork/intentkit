import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.admin.api import admin_router_readonly
from app.admin.health import health_router
from app.config.config import config
from app.entrypoints.web import chat_router_readonly
from models.db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(**config.db)
    logger.info("Readonly API server starting")
    yield
    logger.info("Readonly API server shutting down")


app = FastAPI(lifespan=lifespan)

app.include_router(health_router)
app.include_router(admin_router_readonly)
app.include_router(chat_router_readonly)
