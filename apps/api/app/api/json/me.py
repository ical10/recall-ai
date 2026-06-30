from fastapi import APIRouter

from app.api.deps import OptionalUserDep
from app.schemas.me import MeResponse

router = APIRouter()


@router.get("/me")
async def api_me(user: OptionalUserDep) -> MeResponse | None:
    if user is None:
        return None
    return MeResponse.model_validate(user)
