from fastapi import APIRouter

from app.api.deps import SessionDep, UserDep
from app.schemas.batch import DailyBatch, RatingsBody, SyncResult
from app.services.daily_batch import build_daily_batch
from app.services.rating_sync import apply_ratings

router = APIRouter()


@router.get("/review/batch", response_model=DailyBatch)
async def api_review_batch(session: SessionDep, user: UserDep) -> DailyBatch:
    return await build_daily_batch(session, user)


@router.post("/review/ratings", response_model=SyncResult)
async def api_post_ratings(
    session: SessionDep,
    user: UserDep,
    body: RatingsBody,
) -> SyncResult:
    return await apply_ratings(session, user, body.ratings)
