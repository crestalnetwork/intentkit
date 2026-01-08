from app.local.api import local_router
from app.local.health import health_router
from app.local.metadata import metadata_router
from app.local.schema import schema_router

__all__ = [
    "local_router",
    "health_router",
    "schema_router",
    "metadata_router",
]
