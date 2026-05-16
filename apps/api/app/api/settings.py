from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import Response

from app.api.deps import SessionDep, UserDep, templates
from app.services.interests import TOPIC_TAGS, is_valid_tag

router = APIRouter()


@router.get("/settings")
async def settings_page(request: Request, user: UserDep) -> Response:
    return templates.TemplateResponse(
        request,
        "pages/settings.html",
        {
            "user": user,
            "all_tags": TOPIC_TAGS,
            "selected_tags": set(user.interest_tags or ()),
        },
    )


@router.post("/settings/interests")
async def update_interests(
    request: Request,
    session: SessionDep,
    user: UserDep,
    tags: Annotated[list[str] | None, Form()] = None,
) -> Response:
    cleaned: list[str] = []
    for t in tags or []:
        if not is_valid_tag(t):
            raise HTTPException(status_code=422, detail=f"unknown tag: {t}")
        cleaned.append(t)
    user.interest_tags = cleaned
    await session.merge(user)
    await session.commit()
    return templates.TemplateResponse(
        request,
        "partials/interests-form.html",
        {
            "user": user,
            "all_tags": TOPIC_TAGS,
            "selected_tags": set(cleaned),
            "saved": True,
        },
    )


@router.post("/milestones/seen")
async def mark_milestone_seen(request: Request, session: SessionDep, user: UserDep) -> Response:
    user.last_milestone_seen = user.last_personalized_milestone
    await session.merge(user)
    await session.commit()
    return Response(status_code=200, headers={"HX-Redirect": "/review"})
