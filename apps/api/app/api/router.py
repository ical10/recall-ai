from fastapi import APIRouter

from app.api.reviews import router as reviews_router

router = APIRouter()
router.include_router(reviews_router)
