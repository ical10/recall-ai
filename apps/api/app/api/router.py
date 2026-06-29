from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.json import router as json_router
from app.api.vocab import router as vocab_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(vocab_router)
router.include_router(json_router)
