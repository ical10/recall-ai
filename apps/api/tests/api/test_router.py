from fastapi import APIRouter

from app.api.router import router


def test_router_is_an_apirouter() -> None:
    assert isinstance(router, APIRouter)


def test_router_includes_review_endpoints() -> None:
    paths = {route.path for route in router.routes}
    assert "/review" in paths
    assert "/review/{review_id}/reveal" in paths
    assert "/review/{review_id}/rate" in paths
