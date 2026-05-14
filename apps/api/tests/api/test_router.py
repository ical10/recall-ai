from fastapi import APIRouter

from app.api.router import router


def test_router_is_an_apirouter() -> None:
    assert isinstance(router, APIRouter)


def test_review_routes_are_registered() -> None:
    from app.api.router import router

    paths = [route.path for route in router.routes]  # type: ignore[union-attr]
    assert "/review" in paths


def test_main_app_has_session_middleware() -> None:
    from starlette.middleware.sessions import SessionMiddleware

    from app.main import app

    middleware_types = [m.cls for m in app.user_middleware]
    assert SessionMiddleware in middleware_types
