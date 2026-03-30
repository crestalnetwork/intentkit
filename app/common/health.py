from fastapi import APIRouter

health_router = APIRouter()


@health_router.get("/health", include_in_schema=False)
async def health_check():
    return {"status": "healthy"}
