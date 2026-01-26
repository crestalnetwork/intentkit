from app.local.agent import agent_router
from app.local.autonomous import autonomous_router
from app.local.chat import chat_router
from app.local.content import content_router
from app.local.debug import debug_router
from app.local.health import health_router
from app.local.metadata import metadata_router
from app.local.schema import schema_router

__all__ = [
    "agent_router",
    "autonomous_router",
    "chat_router",
    "content_router",
    "debug_router",
    "health_router",
    "schema_router",
    "metadata_router",
]
