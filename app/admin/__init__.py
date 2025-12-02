from app.admin.api import admin_router
from app.admin.credit import credit_router
from app.admin.health import health_router
from app.admin.metadata import metadata_router
from app.admin.schema import schema_router
from app.admin.user import user_router

__all__ = [
    "admin_router",
    "health_router",
    "schema_router",
    "credit_router",
    "metadata_router",
    "user_router",
    "agent_generator_router",
]
