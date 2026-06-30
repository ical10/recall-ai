from fastapi import APIRouter, HTTPException

from app.api.deps import SessionDep, UserDep
from app.schemas.settings import InterestTagsUpdate, UserSettings
from app.services.interests import TOPIC_TAGS, is_valid_tag

router = APIRouter()


@router.get("/settings", response_model=UserSettings)
async def api_get_settings(user: UserDep) -> UserSettings:
    return UserSettings(
        interest_tags=user.interest_tags or [],
        all_tags=list(TOPIC_TAGS),
    )


@router.put("/settings/interests", response_model=UserSettings)
async def api_update_interests(
    session: SessionDep,
    user: UserDep,
    body: InterestTagsUpdate,
) -> UserSettings:
    for tag in body.tags:
        if not is_valid_tag(tag):
            raise HTTPException(status_code=422, detail=f"unknown tag: {tag}")
    user.interest_tags = body.tags
    await session.merge(user)
    await session.commit()
    return UserSettings(
        interest_tags=user.interest_tags,
        all_tags=list(TOPIC_TAGS),
    )
