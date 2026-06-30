from fastapi import APIRouter, Query

from app.api.deps import SessionDep, UserDep
from app.schemas.vocab import VocabListResponse
from app.services.archive import paginate_user_vocab

router = APIRouter()


@router.get("/archive", response_model=VocabListResponse)
async def api_list_archive(
    session: SessionDep,
    user: UserDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> VocabListResponse:
    return await paginate_user_vocab(session, user, page=page, page_size=page_size)
