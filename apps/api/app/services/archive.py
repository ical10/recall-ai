from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.vocab import VocabListResponse, VocabRead


async def paginate_user_vocab(
    session: AsyncSession,
    user: User,
    *,
    page: int = 1,
    page_size: int = 20,
) -> VocabListResponse:
    total = (
        await session.execute(select(func.count(Review.id)).where(Review.user_id == user.id))
    ).scalar_one()

    rows = (
        (
            await session.execute(
                select(VocabItem)
                .join(Review, Review.vocab_item_id == VocabItem.id)
                .where(Review.user_id == user.id)
                .order_by(VocabItem.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return VocabListResponse(
        items=[VocabRead.model_validate(v) for v in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )
