from fastapi import APIRouter

from app.api.deps import SessionDep, UserDep
from app.schemas.stats import UserStats
from app.services.stats import compute_user_stats

router = APIRouter()


@router.get("/dashboard", response_model=UserStats)
async def api_dashboard(session: SessionDep, user: UserDep) -> UserStats:
    return await compute_user_stats(session, user)
