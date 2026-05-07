from fastapi import APIRouter

from app.api.dashboard import router as dashboard_router

router = APIRouter()
router.include_router(dashboard_router)
