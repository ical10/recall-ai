from fastapi import APIRouter

from app.api.router import router


def test_router_is_an_apirouter() -> None:
    assert isinstance(router, APIRouter)


def test_json_routes_are_registered() -> None:
    paths = [route.path for route in router.routes]
    assert "/api/dashboard" in paths
    assert "/api/review/batch" in paths
    assert "/api/me" in paths
    assert "/api/settings" in paths
    assert "/api/archive" in paths


def test_main_app_has_session_middleware() -> None:
    from starlette.middleware.sessions import SessionMiddleware

    from app.main import app

    middleware_types = [m.cls for m in app.user_middleware]
    assert SessionMiddleware in middleware_types
