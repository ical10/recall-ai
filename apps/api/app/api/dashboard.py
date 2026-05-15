from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from app.api.deps import SessionDep, UserDep, templates
from app.services.stats import compute_user_stats

router = APIRouter()


@router.get("/")
async def index() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@router.get("/dashboard")
async def dashboard(
    request: Request,
    session: SessionDep,
    user: UserDep,
) -> Response:
    stats = await compute_user_stats(session, user)
    review_language = ""
    if "session" in request.scope:
        review_language = request.session.get("review_language", "")
    return templates.TemplateResponse(
        request,
        "pages/dashboard.html",
        {"stats": stats, "user": user, "review_language": review_language},
    )
