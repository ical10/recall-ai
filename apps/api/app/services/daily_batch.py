from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.batch import Card, DailyBatch


async def build_daily_batch(session: AsyncSession, user: User) -> DailyBatch:
    user_tz = ZoneInfo(user.timezone)
    now = datetime.now(user_tz)
    start_of_today = datetime.combine(now.date(), datetime.min.time(), tzinfo=user_tz)
    end_of_today = start_of_today + timedelta(days=1)

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
            )
            .join(VocabItem, Review.vocab_item_id == VocabItem.id)
            .where(
                Review.user_id == user.id,
                Review.suspended.is_(False),
                Review.due_at < end_of_today,
                VocabItem.definition != "",
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
            word_audio_url=None,
            example_audio_url=None,
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
        ) in rows
    ]

    return DailyBatch(cards=cards)
