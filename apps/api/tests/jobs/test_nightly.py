import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.jobs import content_gen, nightly


def test_run_skips_all_stages_when_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = AsyncMock()
    connection.__aenter__.side_effect = ConnectionRefusedError("database unavailable")
    monkeypatch.setattr(AsyncEngine, "connect", lambda _: connection)

    stages = {
        name: AsyncMock()
        for name in (
            "generate_shared_pool",
            "run_daily",
            "generate_personalized_for_all",
            "backfill_audio",
        )
    }
    for name, stage in stages.items():
        monkeypatch.setattr(content_gen, name, stage)

    asyncio.run(nightly.run())

    for stage in stages.values():
        stage.assert_not_awaited()


def test_run_skips_before_connect_when_database_url_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    connect = Mock(return_value=AsyncMock())
    monkeypatch.setattr(AsyncEngine, "connect", connect)
    stages = {
        name: AsyncMock()
        for name in (
            "generate_shared_pool",
            "run_daily",
            "generate_personalized_for_all",
            "backfill_audio",
        )
    }
    for name, stage in stages.items():
        monkeypatch.setattr(content_gen, name, stage)
    caplog.set_level("INFO", logger="app.jobs.nightly")

    asyncio.run(nightly.run())

    connect.assert_not_called()
    for stage in stages.values():
        stage.assert_not_awaited()
    assert "nightly_skipped_database_unreachable" in caplog.messages


def test_run_awaits_the_steps_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []
    connection = AsyncMock()
    monkeypatch.setattr(AsyncEngine, "connect", lambda _: connection)

    async def fake_shared_pool(count: int) -> dict[str, int]:
        calls.append(("generate_shared_pool", count))
        return {"vocab_created": 0}

    async def fake_run_daily(batch_size: int) -> dict[str, int]:
        calls.append(("run_daily", batch_size))
        return {"succeeded": 0, "failed": 0}

    async def fake_personalized_for_all(count: int) -> dict[str, int]:
        calls.append(("generate_personalized_for_all", count))
        return {"total_vocab_created": 0, "users_processed": 0}

    async def fake_backfill_audio(batch_size: int) -> dict[str, int]:
        calls.append(("backfill_audio", batch_size))
        return {"rendered": 0, "skipped": 0}

    monkeypatch.setattr(content_gen, "generate_shared_pool", fake_shared_pool)
    monkeypatch.setattr(content_gen, "run_daily", fake_run_daily)
    monkeypatch.setattr(content_gen, "generate_personalized_for_all", fake_personalized_for_all)
    monkeypatch.setattr(content_gen, "backfill_audio", fake_backfill_audio)

    asyncio.run(nightly.run())

    assert calls == [
        ("generate_shared_pool", 10),
        ("run_daily", 25),
        ("generate_personalized_for_all", 5),
        ("backfill_audio", 50),
    ]


def test_should_run_false_without_env_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.delenv("NIGHTLY_FORCE", raising=False)

    assert nightly.should_run() is False


def test_should_run_true_in_railway_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    monkeypatch.delenv("NIGHTLY_FORCE", raising=False)

    assert nightly.should_run() is True


def test_should_run_false_in_railway_pr_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "recall-ai-pr-42")
    monkeypatch.delenv("NIGHTLY_FORCE", raising=False)

    assert nightly.should_run() is False


def test_should_run_true_when_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAILWAY_ENVIRONMENT_NAME", raising=False)
    monkeypatch.setenv("NIGHTLY_FORCE", "1")

    assert nightly.should_run() is True
