from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.db import SessionLocal
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.services.enrichment import apply_enrichment
from app.services.enrollment import enroll_new_vocab
from app.services.llm import LLMClient, LLMValidationFailure
from app.services.selection import select_unenriched
from app.services.tts import ensure_audio
from app.services.vocab_generation import generate_vocab_batch

logger = logging.getLogger(__name__)


@celery_app.task(name="content_gen.run_daily", max_retries=3)  # type: ignore[untyped-decorator]
def run_daily(batch_size: int = 25) -> dict[str, int]:
    return asyncio.run(_run_daily(batch_size))


async def _run_daily(batch_size: int) -> dict[str, int]:
    succeeded = 0
    failed = 0
    async with SessionLocal() as session:
        items = await select_unenriched(session, batch_size)
        if not items:
            return {"succeeded": 0, "failed": 0}
        llm = LLMClient()
        now = datetime.now(UTC)
        for item in items:
            outcome = apply_enrichment(item, llm, now=now)
            if outcome.ready:
                succeeded += 1
            else:
                logger.warning(
                    "content_gen_item_failed",
                    extra={
                        "vocab_item_id": str(item.id),
                        "attempts": outcome.llm_attempts,
                        "total_attempts": item.enrichment_attempts,
                    },
                )
                failed += 1
        await session.commit()
    return {"succeeded": succeeded, "failed": failed}


@celery_app.task(name="content_gen.generate_shared_pool", max_retries=2)  # type: ignore[untyped-decorator]
def generate_shared_pool(count: int = 10) -> dict[str, int | str]:
    return asyncio.run(_generate_shared_pool(count))


async def _generate_shared_pool(count: int) -> dict[str, int | str]:
    async with SessionLocal() as session:
        # Same-day idempotency: if any shared_pool row exists from today (UTC),
        # skip without touching the LLM. Protects against accidental double-fires
        # (manual `celery call`, two beat processes, retried tasks).
        start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        already = (
            await session.execute(
                select(VocabItem.id)
                .where(VocabItem.source == "shared_pool", VocabItem.created_at >= start_of_day)
                .limit(1)
            )
        ).scalar_one_or_none()
        if already is not None:
            logger.info("shared_pool_skipped_already_ran_today")
            return {"skipped": "already_ran_today"}

        exclude_tokens = list(
            (
                await session.execute(
                    select(VocabItem.token)
                    .where(VocabItem.language == "en")
                    .order_by(VocabItem.created_at.desc())
                    .limit(500)
                )
            )
            .scalars()
            .all()
        )

        llm = LLMClient()
        try:
            batch = generate_vocab_batch(
                llm, language="en", count=count, exclude_tokens=exclude_tokens
            )
        except LLMValidationFailure as e:
            logger.warning(
                "shared_pool_validation_exhausted",
                extra={"attempts": e.attempts},
            )
            return {"succeeded": 0, "failed": 1, "reason": "validation_exhausted"}

        user_ids = list((await session.execute(select(User.id))).scalars().all())
        vocab_created, reviews_created = await enroll_new_vocab(
            session, batch.items, source="shared_pool", user_ids=user_ids
        )
        await session.commit()

    return {"vocab_created": vocab_created, "reviews_created": reviews_created}


@celery_app.task(name="content_gen.generate_personalized", max_retries=2)  # type: ignore[untyped-decorator]
def generate_personalized(user_id: str, count: int = 5) -> dict[str, int | str]:
    return asyncio.run(_generate_personalized(user_id, count))


async def _generate_personalized(user_id: str, count: int = 5) -> dict[str, int | str]:
    uid = UUID(user_id)
    async with SessionLocal() as session:
        user = await session.get(User, uid)
        if user is None:
            logger.warning("personalized_skipped_user_missing", extra={"user_id": user_id})
            return {"skipped": "user_missing"}

        total = (
            await session.execute(
                select(func.count(Review.id)).where(
                    Review.user_id == uid, Review.last_reviewed_at.is_not(None)
                )
            )
        ).scalar_one()
        current_milestone = (int(total) // 30) * 30
        if current_milestone > 0 and user.last_personalized_milestone >= current_milestone:
            logger.info(
                "personalized_skipped_already_fired_for_milestone",
                extra={"user_id": user_id, "milestone": current_milestone},
            )
            return {
                "skipped": "already_fired_for_milestone",
                "milestone": current_milestone,
            }

        llm = LLMClient()
        result = await _generate_personalized_batch(session, user, count, llm)
        if "vocab_created" in result:
            user.last_personalized_milestone = current_milestone
        await session.commit()

    return result


async def _generate_personalized_batch(
    session: AsyncSession,
    user: User,
    count: int,
    llm: LLMClient,
) -> dict[str, int | str]:
    global_tokens = list(
        (
            await session.execute(
                select(VocabItem.token)
                .where(VocabItem.language == "en")
                .order_by(VocabItem.created_at.desc())
                .limit(500)
            )
        )
        .scalars()
        .all()
    )
    user_tokens = list(
        (
            await session.execute(
                select(VocabItem.token)
                .join(Review, Review.vocab_item_id == VocabItem.id)
                .where(Review.user_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    exclude_tokens = list({*global_tokens, *user_tokens})

    try:
        batch = generate_vocab_batch(
            llm,
            language="en",
            count=count,
            exclude_tokens=exclude_tokens,
            interests=user.interest_tags or None,
        )
    except LLMValidationFailure as e:
        logger.warning(
            "personalized_validation_exhausted",
            extra={"user_id": str(user.id), "attempts": e.attempts},
        )
        return {"succeeded": 0, "failed": 1, "reason": "validation_exhausted"}

    vocab_created, reviews_created = await enroll_new_vocab(
        session, batch.items, source="personalized", user_ids=[user.id]
    )
    return {"vocab_created": vocab_created, "reviews_created": reviews_created}


@celery_app.task(name="content_gen.generate_personalized_for_all")  # type: ignore[untyped-decorator]
def generate_personalized_for_all(count: int = 5) -> dict[str, int | str]:
    return asyncio.run(_generate_personalized_for_all(count))


async def _generate_personalized_for_all(count: int) -> dict[str, int | str]:
    async with SessionLocal() as session:
        user_ids = list((await session.execute(select(User.id))).scalars().all())

    if not user_ids:
        return {"total_vocab_created": 0, "users_processed": 0}

    total_created = 0
    users_processed = 0
    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    for uid in user_ids:
        async with SessionLocal() as session:
            user = await session.get(User, uid)
            if user is None:
                continue

            existing = (
                (
                    await session.execute(
                        select(VocabItem)
                        .join(Review, Review.vocab_item_id == VocabItem.id)
                        .where(VocabItem.source == "personalized", Review.user_id == uid)
                    )
                )
                .scalars()
                .all()
            )
            if any(
                v.created_at is not None
                and (
                    (v.created_at.tzinfo is not None and v.created_at >= start_of_day)
                    or (
                        v.created_at.tzinfo is None
                        and v.created_at.replace(tzinfo=UTC) >= start_of_day
                    )
                )
                for v in existing
            ):
                continue

            llm = LLMClient()

            result = await _generate_personalized_batch(session, user, count, llm)
            vc = result.get("vocab_created")
            if isinstance(vc, int):
                total_created += vc
                users_processed += 1
            await session.commit()

    return {"total_vocab_created": total_created, "users_processed": users_processed}


@celery_app.task(name="content_gen.render_audio")  # type: ignore[untyped-decorator]
def render_audio(vocab_item_id: str) -> dict[str, str]:
    return asyncio.run(_render_audio(vocab_item_id))


async def _render_audio(vocab_item_id: str) -> dict[str, str]:
    vid = UUID(vocab_item_id)
    async with SessionLocal() as session:
        vocab = await session.get(VocabItem, vid)
        if vocab is None:
            return {"status": "not_found"}

        if vocab.word_audio_url and vocab.example_audio_url:
            return {"status": "already_rendered"}

        rendered = ensure_audio(vocab)
        await session.commit()

    return {
        "status": "rendered" if rendered else "skipped",
        "word_audio_url": vocab.word_audio_url or "",
        "example_audio_url": vocab.example_audio_url or "",
    }


@celery_app.task(name="content_gen.backfill_audio")  # type: ignore[untyped-decorator]
def backfill_audio(batch_size: int = 100) -> dict[str, int]:
    return asyncio.run(_backfill_audio(batch_size))


async def _backfill_audio(batch_size: int) -> dict[str, int]:
    rendered = 0
    skipped = 0
    async with SessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(VocabItem.id)
                    .where(
                        VocabItem.definition != "",
                        VocabItem.word_audio_url.is_(None),
                    )
                    .limit(batch_size)
                )
            )
            .scalars()
            .all()
        )

        for vid in rows:
            vocab = await session.get(VocabItem, vid)
            if vocab is None:
                continue

            if ensure_audio(vocab):
                rendered += 1
            else:
                skipped += 1

        await session.commit()

    return {"rendered": rendered, "skipped": skipped}
