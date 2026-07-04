"""Local API: single-user, unauthenticated reference API for the bundled
`frontend/`. Intentionally self-contained — see `app/__init__.py` for why
this is kept separate from `app/team` despite the similar routes."""

from app.local.agent import agent_router
from app.local.autonomous import autonomous_router
from app.local.chat import chat_router
from app.local.content import content_router
from app.local.health import health_router
from app.local.lead import lead_router
from app.local.link import link_router
from app.local.metadata import metadata_router
from app.local.public import public_router
from app.local.schema import schema_router
from app.local.wallet import wallet_router
from app.local.wechat import wechat_router

__all__ = [
    "agent_router",
    "autonomous_router",
    "chat_router",
    "content_router",
    "health_router",
    "lead_router",
    "link_router",
    "public_router",
    "schema_router",
    "wallet_router",
    "metadata_router",
    "wechat_router",
]
