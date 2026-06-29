from fastapi import APIRouter

from app.api.json.archive import router as archive_router
from app.api.json.dashboard import router as dashboard_router
from app.api.json.review import router as review_router
from app.api.json.settings import router as settings_router

router = APIRouter(prefix="/api")
router.include_router(dashboard_router)
router.include_router(review_router)
router.include_router(settings_router)
router.include_router(archive_router)
