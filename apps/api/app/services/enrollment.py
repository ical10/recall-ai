from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample


async def enroll_new_vocab(
    session: AsyncSession,
    examples: list[SimpleVocabExample],
    *,
    source: str,
    user_ids: list[UUID],
) -> tuple[int, int]:
    """Add new shared Vocab Items and enroll the given users in each.

    INSERT-time dedupe on the (token, language) unique constraint is the CORRECTNESS
    gate against duplicate tokens — the capped exclusion list upstream is only a
    cost-saver, and the LLM may still propose a token outside the recent window. For
    each newly-created Vocab Item, create one Review per user not already enrolled
    (Enrollment). Returns (vocab_created, reviews_created). No commit — caller owns it.
    """
    now = datetime.now(UTC)
    vocab_created = 0
    reviews_created = 0
    for example in examples:
        vocab = VocabItem(
            token=example.token,
            language="en",
            definition=example.definition,
            example_sentence=example.example,
            source=source,
        )
        session.add(vocab)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            continue
        vocab_created += 1
        for uid in user_ids:
            exists = (
                await session.execute(
                    select(func.count(Review.id)).where(
                        Review.user_id == uid, Review.vocab_item_id == vocab.id
                    )
                )
            ).scalar_one()
            if exists == 0:
                session.add(Review(user_id=uid, vocab_item_id=vocab.id, due_at=now))
                reviews_created += 1
    return vocab_created, reviews_created
