from sqlalchemy.orm import DeclarativeBase

from app.models.base import Base, TimestampMixin
from app.models.user import User


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
        "created_at",
        "updated_at",
    }
    assert cols["email"].unique is True
    assert cols["google_id"].unique is True
    assert cols["email"].nullable is False
    assert cols["google_id"].nullable is False
    assert cols["avatar_url"].nullable is True
