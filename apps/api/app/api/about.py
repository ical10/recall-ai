from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.api.deps import templates

router = APIRouter()


@router.get("/about")
async def about(request: Request) -> Response:
    return templates.TemplateResponse(request, "pages/about.html")
