from fastapi import APIRouter

from app.api.vocab import router as vocab_router

router = APIRouter()
router.include_router(vocab_router)
