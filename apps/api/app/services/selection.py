from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.vocab_item import VocabItem


def select_unenriched(session: Session, limit: int) -> list[VocabItem]:
    if limit <= 0:
        return []
    stmt = (
        select(VocabItem)
        .where(or_(VocabItem.definition == "", VocabItem.example_sentence.is_(None)))
        .order_by(VocabItem.created_at.asc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())
