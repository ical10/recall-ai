from fastapi import APIRouter

from app.api.deps import SessionDep, UserDep
from app.models.user import User

router = APIRouter()


@router.post("/milestones/seen", status_code=204)
async def api_mark_milestone_seen(session: SessionDep, user: UserDep) -> None:
    u = await session.get(User, user.id)
    if u is None:
        return
    u.last_milestone_seen = u.last_personalized_milestone
    await session.commit()
