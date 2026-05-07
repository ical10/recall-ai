from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import delete, func, select

from app.api.deps import CurrentUserDep, SessionDep
from app.models.review import Review
from app.models.vocab_item import VocabItem
from app.schemas.vocab import VocabCreate, VocabListResponse, VocabRead

router = APIRouter()


@router.get("/vocab", response_model=VocabListResponse)
async def list_vocab(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> VocabListResponse:
    total = (await session.execute(select(func.count(VocabItem.id)))).scalar_one()
    rows = (
        (
            await session.execute(
                select(VocabItem)
                .order_by(VocabItem.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return VocabListResponse(
        items=[VocabRead.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post("/vocab", status_code=201)
async def create_vocab(
    body: VocabCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUserDep,
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
        response.status_code = 200
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
    vocab_id: UUID,
    session: SessionDep,
    user: CurrentUserDep,
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


@router.delete("/vocab/{vocab_id}", status_code=204)
async def delete_vocab(
    vocab_id: UUID,
    session: SessionDep,
    _user: CurrentUserDep,
) -> None:
    result = await session.execute(delete(VocabItem).where(VocabItem.id == vocab_id))
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404)
    await session.commit()
