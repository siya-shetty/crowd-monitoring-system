from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.videos import router as videos_router
from app.api.v1.zones import router as zones_router
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(videos_router)
api_router.include_router(zones_router)
