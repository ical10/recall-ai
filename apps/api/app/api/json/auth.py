from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/auth/logout", status_code=204)
async def api_logout(request: Request) -> None:
    request.session.clear()
