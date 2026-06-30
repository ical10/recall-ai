from fastapi import APIRouter

from app.api.json.archive import router as archive_router
from app.api.json.auth import router as auth_router
from app.api.json.dashboard import router as dashboard_router
from app.api.json.me import router as me_router
from app.api.json.milestones import router as milestones_router
from app.api.json.review import router as review_router
from app.api.json.settings import router as settings_router

router = APIRouter(prefix="/api")
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(me_router)
router.include_router(milestones_router)
router.include_router(review_router)
router.include_router(settings_router)
router.include_router(archive_router)
