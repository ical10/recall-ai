from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample
from app.services.llm import LLMValidationFailure


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_run_daily_persists_definition_and_example_to_vocab_item(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    from app.workers import content_gen

    with session_factory() as setup:
        setup.add_all(
            [
                VocabItem(token="alpha", language="en", definition="", example_sentence=None),
                VocabItem(token="beta", language="en", definition="", example_sentence=None),
            ]
        )
        setup.commit()

    fake_llm = type(
        "FakeLLM",
        (),
        {
            "complete": lambda self, prompt, schema: SimpleVocabExample(
                token="alpha" if "alpha" in prompt else "beta",
                definition="A definition long enough to satisfy the schema bounds.",
                example=(
                    "The alpha was here today."
                    if "alpha" in prompt
                    else "The beta arrived later in the day."
                ),
            ),
        },
    )

    monkeypatch.setattr(content_gen, "SyncSessionLocal", session_factory)
    monkeypatch.setattr(content_gen, "LLMClient", lambda: fake_llm())

    result = content_gen.run_daily(batch_size=2)

    assert result == {"succeeded": 2, "failed": 0}
    with session_factory() as check:
        items = check.query(VocabItem).order_by(VocabItem.token).all()
        assert all(i.definition for i in items)
        assert all(i.example_sentence for i in items)


def test_run_daily_skips_failed_items_and_continues_batch(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    from app.workers import content_gen

    with session_factory() as setup:
        setup.add_all(
            [
                VocabItem(token="alpha", language="en", definition="", example_sentence=None),
                VocabItem(token="beta", language="en", definition="", example_sentence=None),
                VocabItem(token="gamma", language="en", definition="", example_sentence=None),
            ]
        )
        setup.commit()

    def fake_complete(self: object, prompt: str, schema: type) -> SimpleVocabExample:
        if "beta" in prompt:
            raise LLMValidationFailure(
                "validation failed after 3 attempts", attempts=3, last_error=None
            )
        token = "alpha" if "alpha" in prompt else "gamma"
        return SimpleVocabExample(
            token=token,
            definition="A definition long enough to satisfy the schema bounds.",
            example=f"The {token} word appears in this example sentence.",
        )

    fake_llm = type("FakeLLM", (), {"complete": fake_complete})

    monkeypatch.setattr(content_gen, "SyncSessionLocal", session_factory)
    monkeypatch.setattr(content_gen, "LLMClient", lambda: fake_llm())

    result = content_gen.run_daily(batch_size=10)

    assert result == {"succeeded": 2, "failed": 1}
    with session_factory() as check:
        by_token = {i.token: i for i in check.query(VocabItem).all()}
        assert by_token["alpha"].definition
        assert by_token["gamma"].definition
        assert by_token["beta"].definition == ""


def test_run_daily_returns_zero_counts_when_no_unenriched(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    from app.workers import content_gen

    constructed: list[bool] = []

    def fake_constructor() -> object:
        constructed.append(True)
        return object()

    monkeypatch.setattr(content_gen, "SyncSessionLocal", session_factory)
    monkeypatch.setattr(content_gen, "LLMClient", fake_constructor)

    result = content_gen.run_daily(batch_size=10)

    assert result == {"succeeded": 0, "failed": 0}
    assert constructed == []


def test_run_daily_respects_batch_size(
    monkeypatch: pytest.MonkeyPatch, session_factory: sessionmaker[Session]
) -> None:
    from app.workers import content_gen

    with session_factory() as setup:
        for i in range(50):
            setup.add(
                VocabItem(
                    token=f"word{i:02d}",
                    language="en",
                    definition="",
                    example_sentence=None,
                )
            )
        setup.commit()

    call_count = 0

    def fake_complete(self: object, prompt: str, schema: type) -> SimpleVocabExample:
        nonlocal call_count
        call_count += 1
        # Pull the token out of the prompt to satisfy the schema's "example contains token" rule.
        token = prompt.split("'")[1]
        return SimpleVocabExample(
            token=token,
            definition="A definition long enough to satisfy the schema bounds.",
            example=f"The {token} word appears in this example sentence.",
        )

    fake_llm = type("FakeLLM", (), {"complete": fake_complete})

    monkeypatch.setattr(content_gen, "SyncSessionLocal", session_factory)
    monkeypatch.setattr(content_gen, "LLMClient", lambda: fake_llm())

    content_gen.run_daily(batch_size=5)

    assert call_count == 5


def test_run_daily_is_registered_as_celery_task() -> None:
    from app.core.celery_app import celery_app
    from app.workers.content_gen import run_daily

    assert run_daily.name == "content_gen.run_daily"
    assert "content_gen.run_daily" in celery_app.tasks
