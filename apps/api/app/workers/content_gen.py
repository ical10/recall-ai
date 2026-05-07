from __future__ import annotations

import logging

from celery import Task

from app.core.celery_app import celery_app
from app.core.db_sync import SyncSessionLocal
from app.services.enrichment import enrich_vocab_item
from app.services.llm import LLMClient, LLMValidationFailure
from app.services.selection import select_unenriched

logger = logging.getLogger(__name__)


@celery_app.task(name="content_gen.run_daily", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def run_daily(self: Task, batch_size: int = 25) -> dict[str, int]:
    succeeded = 0
    failed = 0
    with SyncSessionLocal() as session:
        items = select_unenriched(session, batch_size)
        if not items:
            return {"succeeded": 0, "failed": 0}
        llm = LLMClient()
        for item in items:
            try:
                result = enrich_vocab_item(item, llm)
                item.definition = result.definition
                item.example_sentence = result.example
                succeeded += 1
            except LLMValidationFailure as e:
                logger.warning(
                    "content_gen_item_failed",
                    extra={"vocab_item_id": str(item.id), "attempts": e.attempts},
                )
                failed += 1
        session.commit()
    return {"succeeded": succeeded, "failed": failed}
