from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select

from app.api.deps import SessionDep, UserDep
from app.models.review import Review
from app.models.vocab_item import VocabItem
from app.schemas.vocab import VocabCreate, VocabRead

router = APIRouter()


@router.post("/vocab", status_code=201, response_model=VocabRead)
async def create_vocab(
    session: SessionDep,
    user: UserDep,
    body: VocabCreate,
) -> VocabRead:
    existing = (
        await session.execute(
            select(VocabItem).where(
                VocabItem.token == body.token,
                VocabItem.language == body.language,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        item = existing
    else:
        item = VocabItem(token=body.token, language=body.language, definition="")
        session.add(item)
        await session.flush()
    review = (
        await session.execute(
            select(Review).where(
                Review.user_id == user.id,
                Review.vocab_item_id == item.id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        session.add(
            Review(
                user_id=user.id,
                vocab_item_id=item.id,
                due_at=datetime.now(UTC),
            )
        )
    await session.commit()
    await session.refresh(item)
    return VocabRead.model_validate(item)


@router.patch("/vocab/{vocab_id}/suspend")
async def suspend_vocab(
    session: SessionDep,
    user: UserDep,
    vocab_id: UUID,
) -> dict[str, bool]:
    review = (
        await session.execute(
            select(Review).where(
                Review.user_id == user.id,
                Review.vocab_item_id == vocab_id,
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404)
    review.suspended = not review.suspended
    await session.commit()
    return {"suspended": review.suspended}


@router.delete("/reviews/{vocab_id}", status_code=204)
async def delete_review(
    session: SessionDep,
    user: UserDep,
    vocab_id: UUID,
) -> None:
    exists = (
        await session.execute(
            select(Review.id).where(
                Review.user_id == user.id,
                Review.vocab_item_id == vocab_id,
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404)
    await session.execute(
        delete(Review).where(
            Review.user_id == user.id,
            Review.vocab_item_id == vocab_id,
        )
    )
    await session.commit()
