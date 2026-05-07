import inspect as stdlib_inspect
from typing import Any

from sqlalchemy.inspection import inspect


def test_review_has_vocab_item_relationship() -> None:
    from app.models.review import Review

    rel = inspect(Review).relationships.get("vocab_item")
    assert rel is not None, "Review.vocab_item relationship missing"
    assert rel.lazy == "raise", "expected lazy='raise' to surface accidental N+1"


def test_next_due_review_helper_exists() -> None:
    from app.api.reviews import _next_due_review

    sig = stdlib_inspect.signature(_next_due_review)
    params = list(sig.parameters)
    assert params == ["session", "user_id", "now"], (
        f"_next_due_review signature mismatch: got {params}"
    )


def test_next_due_review_returns_due_review(in_memory_session_factory: Any) -> None:
    import asyncio
    from datetime import UTC, datetime

    from app.api.reviews import _next_due_review
    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    async def run() -> None:
        factory = in_memory_session_factory

        async with factory() as session:
            user = User(email="test@example.com", google_id="gid-1", name="Test")
            session.add(user)
            await session.flush()

            vocab = VocabItem(
                token="apple",
                language="en",
                definition="a fruit",
            )
            session.add(vocab)
            await session.flush()

            now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
            review = Review(
                user_id=user.id,
                vocab_item_id=vocab.id,
                due_at=datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC),
            )
            session.add(review)
            await session.commit()

        async with factory() as session:
            result = await _next_due_review(session, user.id, now)
            assert result is not None, "_next_due_review returned None for a due review"
            assert result.id == review.id

    asyncio.run(run())
