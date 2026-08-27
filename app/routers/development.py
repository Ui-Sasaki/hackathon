"""Development-only API routes."""

from fastapi import APIRouter, Depends

from app.api_support import (
    api_errors,
    application_repository_dependency,
    match_repository_dependency,
    request_repository_dependency,
)
from app.auth import CurrentUser, get_current_user
from app.repositories.applications import ApplicationRepository
from app.repositories.matches import MatchRepository
from app.repositories.requests import RequestRepository
from app.schemas import ResetResponse


router = APIRouter()


async def require_mock_environment() -> None:
    from app.cruds import main as runtime

    if not runtime.MOCK_RESET_ENABLED:
        from fastapi import HTTPException

        raise HTTPException(404, detail={"code": "NOT_FOUND"})


@router.post(
    "/_mock/reset",
    response_model=ResetResponse,
    tags=["Development mock"],
    summary="開発用モックデータを初期化",
    description=(
        "非本番かつMOCK_RESET_ENABLED=trueの場合だけ、認証済み利用者が実行できる。"
        "全モックデータを初期状態へ戻す。"
    ),
    responses=api_errors(401, 404, 500),
)
async def reset_mock(
    _: None = Depends(require_mock_environment),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
    match_repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    runtime.reset_store()
    await repository.reset()
    await application_repository.reset()
    await match_repository.reset()
    return {"reset": True}
