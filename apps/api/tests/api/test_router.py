from fastapi import APIRouter

from app.api.router import router


def test_router_is_an_apirouter() -> None:
    assert isinstance(router, APIRouter)


def test_router_includes_dashboard_routes() -> None:
    routes = [r.path for r in router.routes]  # type: ignore[attr-defined]
    assert "/" in routes
    assert "/dashboard" in routes
