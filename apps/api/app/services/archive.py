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
        await session.execute(
            select(
                VocabItem.id,
                VocabItem.token,
                VocabItem.language,
                VocabItem.part_of_speech,
                VocabItem.definition,
                VocabItem.example_sentence,
            )
            .join(Review, Review.vocab_item_id == VocabItem.id)
            .where(Review.user_id == user.id)
            .order_by(VocabItem.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [
        VocabRead(
            id=vid,
            token=token,
            language=lang,
            part_of_speech=pos,
            definition=defn,
            example_sentence=example,
        )
        for (vid, token, lang, pos, defn, example) in rows
    ]

    return VocabListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=int(total),
    )
