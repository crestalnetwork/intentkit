import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from intentkit.core.agent.tool_registry import get_tool_catalog
from intentkit.models.llm import LLMModelInfo, LLMProvider

logger = logging.getLogger(__name__)

# Create a readonly router for metadata endpoints
metadata_router = APIRouter(tags=["Metadata"])


class LLMModelInfoWithProviderName(LLMModelInfo):
    """LLM model information with provider display name."""

    provider_name: str


@metadata_router.get(
    "/metadata/llms",
    response_model=list[LLMModelInfoWithProviderName],
    summary="Get all LLM models",
    description="Returns a list of all available LLM models in the system",
)
async def get_llms():
    """
    Get all LLM models available in the system.

    **Returns:**
    * `list[LLMModelInfoWithProviderName]` - List of all LLM models with provider display names
    """
    try:
        result_models = []
        for model_info in await LLMModelInfo.get_all():
            provider = LLMProvider(model_info.provider)
            result_models.append(
                LLMModelInfoWithProviderName(
                    **model_info.model_dump(),
                    provider_name=provider.display_name(),
                )
            )
        return result_models
    except Exception as e:
        logger.error("Error getting LLM models: %s", e)
        raise


@metadata_router.get(
    "/metadata/tools",
    summary="Get the toolset catalog",
    description=(
        "Returns the toolset catalog, filtered to what is usable in this "
        "deployment. Keyed by category; each entry carries the category's "
        "title, description, tags, icon name and its individual tools."
    ),
    operation_id="get_tool_catalog",
)
async def get_tools() -> JSONResponse:
    """Get the toolset catalog for building a tool picker.

    Each category is ``{title, description, x-tags, x-icon?, x-web3?, tools}``,
    where ``tools`` maps tool name to ``{title, description}``. Icons are served
    by ``GET /tools/{category}/{x-icon}.{ext}``.

    **Returns:**
    * `JSONResponse` - Catalog keyed by category name
    """
    return JSONResponse(
        content=get_tool_catalog(available_only=True),
        media_type="application/json",
        # Fixed for the lifetime of the deployment (the underlying catalog is
        # built from code and cached), so it is safe to cache in the browser.
        headers={"Cache-Control": "public, max-age=3600"},
    )
