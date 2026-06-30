from sqlalchemy.orm import DeclarativeBase

from app.models.base import Base, TimestampMixin
from app.models.review import Review, ReviewQuality
from app.models.user import User
from app.models.vocab_item import VocabItem


def test_base_is_declarative_base() -> None:
    assert issubclass(Base, DeclarativeBase)


def test_base_uses_naming_convention() -> None:
    convention = Base.metadata.naming_convention
    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["fk"] == "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    assert convention["ix"] == "ix_%(table_name)s_%(column_0_name)s"
    assert convention["uq"] == "uq_%(table_name)s_%(column_0_name)s"
    assert convention["ck"] == "ck_%(table_name)s_%(constraint_name)s"


def test_timestamp_mixin_has_created_at_and_updated_at() -> None:
    # Mixin classes don't have __table__; verify by attribute presence on the mapper-ready columns
    assert hasattr(TimestampMixin, "created_at")
    assert hasattr(TimestampMixin, "updated_at")


def test_user_model_table_and_columns() -> None:
    assert User.__tablename__ == "users"
    cols = {c.name: c for c in User.__table__.columns}
    assert set(cols) == {
        "id",
        "email",
        "google_id",
        "name",
        "avatar_url",
        "timezone",
        "interest_tags",
        "last_personalized_milestone",
        "last_milestone_seen",
        "created_at",
        "updated_at",
    }
    assert cols["email"].unique is True
    assert cols["google_id"].unique is True
    assert cols["email"].nullable is False
    assert cols["google_id"].nullable is False
    assert cols["avatar_url"].nullable is True
    assert cols["timezone"].nullable is False
    assert cols["interest_tags"].nullable is False
    assert cols["last_personalized_milestone"].nullable is False
    assert cols["last_milestone_seen"].nullable is False


def test_user_default_interest_tags_are_kid_friendly_starting_set() -> None:
    from app.models.user import DEFAULT_INTEREST_TAGS

    assert DEFAULT_INTEREST_TAGS == ["animals", "family", "food"]
    assert User.__table__.c.interest_tags.default is not None


def test_vocab_item_model_table_and_columns() -> None:
    assert VocabItem.__tablename__ == "vocab_items"
    cols = {c.name: c for c in VocabItem.__table__.columns}
    assert set(cols) == {
        "id",
        "token",
        "language",
        "part_of_speech",
        "definition",
        "example_sentence",
        "word_audio_url",
        "example_audio_url",
        "enrichment_attempts",
        "last_enrichment_attempted_at",
        "source",
        "created_at",
        "updated_at",
    }
    assert cols["token"].nullable is False
    assert cols["language"].nullable is False
    assert cols["definition"].nullable is False
    assert cols["word_audio_url"].nullable is True
    assert cols["example_audio_url"].nullable is True
    assert cols["enrichment_attempts"].nullable is False
    assert cols["last_enrichment_attempted_at"].nullable is True
    assert cols["source"].nullable is False
    # Composite uniqueness on (token, language)
    uniques = [
        tuple(sorted(c.name for c in u.columns))
        for u in VocabItem.__table__.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("language", "token") in uniques


def test_review_quality_enum_values() -> None:
    assert ReviewQuality.AGAIN.value == 0
    assert ReviewQuality.HARD.value == 2
    assert ReviewQuality.GOOD.value == 4
    assert ReviewQuality.EASY.value == 5


def test_review_model_table_and_columns() -> None:
    assert Review.__tablename__ == "reviews"
    cols = {c.name: c for c in Review.__table__.columns}
    assert set(cols) == {
        "id",
        "user_id",
        "vocab_item_id",
        "ease_factor",
        "interval_days",
        "repetitions",
        "last_reviewed_at",
        "due_at",
        "suspended",
        "created_at",
        "updated_at",
    }
    for name, expected in [
        ("ease_factor", 2.5),
        ("interval_days", 0),
        ("repetitions", 0),
        ("suspended", False),
    ]:
        col = cols[name]
        assert col.default is not None, f"{name} expected a Python-side default"
        assert col.default.arg == expected


def test_vocab_item_composite_unique_has_descriptive_name() -> None:
    uniques = {
        u.name: tuple(sorted(c.name for c in u.columns))
        for u in VocabItem.__table__.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    }
    assert uniques.get("uq_vocab_items_token_language") == ("language", "token")


def test_vocab_item_language_accepts_full_bcp47_tags() -> None:
    # BCP 47 tags can be up to 35 chars (e.g., zh-Hant-TW); String(8) truncates them.
    assert VocabItem.__table__.c.language.type.length >= 35


def test_user_email_has_no_redundant_non_unique_index() -> None:
    email = User.__table__.c.email
    redundant = [ix for ix in User.__table__.indexes if list(ix.columns) == [email]]
    assert redundant == [], "email is already covered by unique=True; a separate Index is redundant"


def test_timestamp_columns_are_timezone_aware() -> None:
    from app.models.user import User

    assert User.__table__.columns["created_at"].type.timezone is True
    assert User.__table__.columns["updated_at"].type.timezone is True


def test_review_has_unique_user_vocab_pair() -> None:
    uniques = [
        tuple(sorted(c.name for c in u.columns))
        for u in Review.__table__.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("user_id", "vocab_item_id") in uniques


def test_review_composite_unique_has_descriptive_name() -> None:
    uniques = {
        u.name: tuple(sorted(c.name for c in u.columns))
        for u in Review.__table__.constraints
        if u.__class__.__name__ == "UniqueConstraint"
    }
    assert uniques.get("uq_reviews_user_id_vocab_item_id") == ("user_id", "vocab_item_id")
