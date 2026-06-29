from fastapi import APIRouter

from app.api.about import router as about_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.json import router as json_router
from app.api.reviews import router as reviews_router
from app.api.settings import router as settings_router
from app.api.vocab import router as vocab_router

router = APIRouter()
router.include_router(about_router)
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(reviews_router)
router.include_router(settings_router)
router.include_router(vocab_router)
router.include_router(json_router)
