from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vocab_item import VocabItem

MAX_ATTEMPTS_BEFORE_COOLDOWN = 3
COOLDOWN_DAYS = 7


async def select_unenriched(session: AsyncSession, limit: int) -> list[VocabItem]:
    """Return up to `limit` VocabItems missing definition or example_sentence and
    not in cooldown, ordered by created_at ASC (oldest first). An item enters
    cooldown after MAX_ATTEMPTS_BEFORE_COOLDOWN consecutive failures; it becomes
    eligible again COOLDOWN_DAYS after its last attempt."""
    if limit <= 0:
        return []
    cooldown_cutoff = datetime.now(UTC) - timedelta(days=COOLDOWN_DAYS)
    stmt = (
        select(VocabItem)
        .where(
            or_(VocabItem.definition == "", VocabItem.example_sentence.is_(None)),
            or_(
                VocabItem.enrichment_attempts < MAX_ATTEMPTS_BEFORE_COOLDOWN,
                VocabItem.last_enrichment_attempted_at.is_(None),
                VocabItem.last_enrichment_attempted_at < cooldown_cutoff,
            ),
        )
        .order_by(VocabItem.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
