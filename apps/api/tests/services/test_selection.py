from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.vocab_item import VocabItem
from app.services.selection import select_unenriched


@pytest.fixture
def sync_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def test_select_unenriched_returns_empty_list_when_limit_zero(sync_session: Session) -> None:
    assert select_unenriched(sync_session, 0) == []


def test_select_unenriched_returns_only_items_missing_definition_or_example(
    sync_session: Session,
) -> None:
    enriched = VocabItem(
        token="full",
        language="en",
        definition="A complete entry with all fields populated.",
        example_sentence="The full entry is here.",
    )
    missing_def = VocabItem(
        token="empty_def",
        language="en",
        definition="",
        example_sentence="Has example but empty definition.",
    )
    missing_ex = VocabItem(
        token="no_ex",
        language="en",
        definition="Has definition but no example.",
        example_sentence=None,
    )
    sync_session.add_all([enriched, missing_def, missing_ex])
    sync_session.commit()

    result = select_unenriched(sync_session, 10)

    tokens = {item.token for item in result}
    assert tokens == {"empty_def", "no_ex"}


def test_select_unenriched_respects_limit_and_orders_by_created_at(
    sync_session: Session,
) -> None:
    from datetime import UTC, datetime, timedelta

    base = datetime(2026, 1, 1, tzinfo=UTC)
    # Insert in reverse chronological order so insertion-order != created_at order.
    for i in reversed(range(5)):
        item = VocabItem(token=f"t{i}", language="en", definition="", example_sentence=None)
        item.created_at = base + timedelta(hours=i)
        item.updated_at = item.created_at
        sync_session.add(item)
    sync_session.commit()

    result = select_unenriched(sync_session, 3)

    assert [item.token for item in result] == ["t0", "t1", "t2"]


def test_select_unenriched_returns_empty_list_when_all_enriched(sync_session: Session) -> None:
    sync_session.add(
        VocabItem(
            token="full",
            language="en",
            definition="A complete entry with all fields populated.",
            example_sentence="The full entry is here.",
        )
    )
    sync_session.commit()

    assert select_unenriched(sync_session, 10) == []
