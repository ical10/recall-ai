from fastapi import APIRouter

from app.api.router import router


def test_router_is_an_apirouter() -> None:
    assert isinstance(router, APIRouter)
