from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import contains_eager

from app.api.deps import SessionDep, UserDep
from app.core.config import get_settings
from app.models.review import Review
from app.models.vocab_item import VocabItem
from app.schemas.pronunciation import PronunciationVerdict
from app.services.pronunciation import evaluate_pronunciation

ALLOWED_MIMES = {"audio/webm", "audio/mp4", "audio/wav", "audio/webm;codecs=opus"}
MAX_AUDIO_BYTES = 2 * 1024 * 1024

router = APIRouter()


@router.post("/review/pronunciation", response_model=PronunciationVerdict)
async def api_pronunciation(
    session: SessionDep,
    user: UserDep,
    vocab_item_id: UUID,
    audio: UploadFile = File(...),  # noqa: B008
) -> PronunciationVerdict:
    settings = get_settings()
    if not settings.stt_provider:
        raise HTTPException(status_code=503, detail="pronunciation not configured")

    content_type = audio.content_type or ""
    mime = content_type.split(";")[0].strip()
    if mime not in {"audio/webm", "audio/mp4", "audio/wav"}:
        raise HTTPException(status_code=400, detail=f"unsupported audio type: {mime}")

    review = (
        await session.execute(
            select(Review)
            .join(VocabItem, Review.vocab_item_id == VocabItem.id)
            .options(contains_eager(Review.vocab_item))
            .where(
                Review.vocab_item_id == vocab_item_id,
                Review.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404, detail="card not found")

    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="audio too large")
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="audio is empty")

    token = review.vocab_item.token
    return await asyncio.to_thread(evaluate_pronunciation, audio_bytes, mime, target=token)
