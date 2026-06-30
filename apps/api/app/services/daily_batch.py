from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.batch import Card, DailyBatch
from app.services.due import due_today_conditions, not_reviewed_today_condition


async def build_daily_batch(session: AsyncSession, user: User) -> DailyBatch:
    rows = (
        await session.execute(
            select(
                Review.id,
                VocabItem.id,
                VocabItem.token,
                VocabItem.definition,
                VocabItem.example_sentence,
                Review.ease_factor,
                Review.interval_days,
                Review.repetitions,
                Review.due_at,
                VocabItem.word_audio_url,
                VocabItem.example_audio_url,
            )
            .join(VocabItem, Review.vocab_item_id == VocabItem.id)
            .where(
                Review.user_id == user.id,
                and_(
                    *due_today_conditions(user.timezone),
                    not_reviewed_today_condition(user.timezone),
                ),
            )
            .order_by(Review.due_at, VocabItem.token)
        )
    ).all()

    cards = [
        Card(
            review_id=review_id,
            vocab_item_id=vocab_id,
            token=token,
            definition=definition,
            example_sentence=example_sentence,
            ease_factor=ease_factor,
            interval_days=interval_days,
            repetitions=repetitions,
            due_at=due_at,
            word_audio_url=word_audio_url,
            example_audio_url=example_audio_url,
        )
        for (
            review_id,
            vocab_id,
            token,
            definition,
            example_sentence,
            ease_factor,
            interval_days,
            repetitions,
            due_at,
            word_audio_url,
            example_audio_url,
        ) in rows
    ]

    return DailyBatch(cards=cards)
