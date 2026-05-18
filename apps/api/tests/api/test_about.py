"""Tests for the public /about page."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app() -> FastAPI:
    from app.api.about import router as about_router

    app = FastAPI()
    app.include_router(about_router)
    return app


def test_about_page_renders_anonymously() -> None:
    client = TestClient(_make_app())
    response = client.get("/about")
    assert response.status_code == 200
    assert b"SM-2" in response.content
