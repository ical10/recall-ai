from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.core.celery_app import celery_app
from app.core.db import SessionLocal
from app.services.enrichment import enrich_vocab_item
from app.services.llm import LLMClient, LLMValidationFailure
from app.services.selection import select_unenriched

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
            item.last_enrichment_attempted_at = now
            try:
                result = enrich_vocab_item(item, llm)
                item.definition = result.definition
                item.example_sentence = result.example
                item.enrichment_attempts = 0
                succeeded += 1
            except LLMValidationFailure as e:
                item.enrichment_attempts += 1
                logger.warning(
                    "content_gen_item_failed",
                    extra={
                        "vocab_item_id": str(item.id),
                        "attempts": e.attempts,
                        "total_attempts": item.enrichment_attempts,
                    },
                )
                failed += 1
        await session.commit()
    return {"succeeded": succeeded, "failed": failed}
