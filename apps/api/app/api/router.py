from fastapi import APIRouter

from app.api.dashboard import router as dashboard_router
from app.api.reviews import router as reviews_router
from app.api.vocab import router as vocab_router

router = APIRouter()
router.include_router(dashboard_router)
router.include_router(reviews_router)
router.include_router(vocab_router)
