from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError


class TestRatingSchemas:
    def test_rating_in_valid(self) -> None:
        from app.schemas.batch import RatingIn

        r = RatingIn(
            rating_id=uuid4(),
            card_id=uuid4(),
            grade=4,
            rated_at=datetime.now(UTC),
        )
        assert r.grade == 4

    def test_rating_in_rejects_invalid_grade(self) -> None:
        from app.schemas.batch import RatingIn

        with pytest.raises(ValidationError):
            RatingIn(
                rating_id=uuid4(),
                card_id=uuid4(),
                grade=3,
                rated_at=datetime.now(UTC),
            )

    def test_rating_in_rejects_negative_grade(self) -> None:
        from app.schemas.batch import RatingIn

        with pytest.raises(ValidationError):
            RatingIn(
                rating_id=uuid4(),
                card_id=uuid4(),
                grade=-1,
                rated_at=datetime.now(UTC),
            )

    def test_ratings_body_valid(self) -> None:
        from app.schemas.batch import RatingIn, RatingsBody

        body = RatingsBody(
            ratings=[
                RatingIn(
                    rating_id=uuid4(),
                    card_id=uuid4(),
                    grade=4,
                    rated_at=datetime.now(UTC),
                ),
            ]
        )
        assert len(body.ratings) == 1

    def test_ratings_body_empty_is_valid(self) -> None:
        from app.schemas.batch import RatingsBody

        body = RatingsBody(ratings=[])
        assert body.ratings == []

    def test_sync_result_defaults(self) -> None:
        from app.schemas.batch import SyncResult

        r = SyncResult(applied=5, skipped=2)
        assert r.applied == 5
        assert r.skipped == 2

    def test_sync_result_non_negative(self) -> None:
        from app.schemas.batch import SyncResult

        with pytest.raises(ValidationError):
            SyncResult(applied=-1, skipped=0)

        with pytest.raises(ValidationError):
            SyncResult(applied=0, skipped=-1)
