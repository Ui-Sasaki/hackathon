"""Application, matching, chat, completion, and dispute API routes."""

from fastapi import APIRouter, Depends, HTTPException

from app.api_support import (
    api_errors,
    application_repository_dependency,
    match_repository_dependency,
    request_repository_dependency,
)
from app.auth import CurrentUser, get_current_user
from app.repositories.applications import ApplicationRepository
from app.repositories.matches import MatchRepository, MatchRepositoryError
from app.repositories.requests import RequestRepository
from app.schemas import (
    ApplicationInput,
    ApplicationListResponse,
    ApplicationResponse,
    CompletionInput,
    DisputeInput,
    MatchResponse,
    MessageInput,
    MessageListResponse,
    MessageResponse,
    SelectionInput,
)
from app.services.applications import (
    create_application as create_application_service,
    withdraw_application as withdraw_application_service,
)
from app.services.requests import require_request


router = APIRouter()


@router.get(
    "/requests/{request_id}/applications",
    response_model=ApplicationListResponse,
    tags=["Applications"],
    summary="自分の依頼の応募者を一覧",
    description="依頼者本人だけが閲覧でき、ブロック関係の応募者は除外する。",
    responses=api_errors(401, 403, 404, 500),
)
async def list_applications(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
):
    from app.cruds import main as runtime

    request_item = await require_request(repository, current_user, request_id)
    if request_item["requesterId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    items = await application_repository.list_for_request(current_user, request_id)
    return {
        "items": [
            {**item, "helper": item.get("helper") or runtime.HELPERS[item["helperId"]]}
            for item in items
            if not runtime.is_blocked_pair(current_user.user_id, item["helperId"])
        ]
    }


@router.post(
    "/requests/{request_id}/applications",
    response_model=ApplicationResponse,
    status_code=201,
    tags=["Applications"],
    summary="公開依頼へ応募",
    description=(
        "認証済み本人を支援者として応募する。自分の依頼、重複応募、"
        "公開中でない依頼には応募できない。"
    ),
    responses=api_errors(401, 403, 404, 409, 422, 500),
)
async def create_application(
    request_id: str,
    body: ApplicationInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
):
    from app.cruds import main as runtime

    request_item = await require_request(repository, current_user, request_id)
    if runtime.is_blocked_pair(
        current_user.user_id, request_item["requesterId"]
    ):
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    return await create_application_service(
        application_repository,
        current_user,
        request_item,
        body.model_dump(),
    )


@router.post(
    "/applications/{application_id}/withdraw",
    response_model=ApplicationResponse,
    tags=["Applications"],
    summary="応募を取り下げ",
    description="応募した本人だけがapplied状態をwithdrawnへ遷移できる。",
    responses=api_errors(401, 403, 404, 409, 500),
)
async def withdraw_application(
    application_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: ApplicationRepository = Depends(application_repository_dependency),
):
    return await withdraw_application_service(
        repository, current_user, application_id
    )


@router.post(
    "/applications/{application_id}/select",
    response_model=MatchResponse,
    status_code=201,
    tags=["Applications"],
    summary="応募者を選択してマッチ成立",
    description=(
        "依頼者本人だけが応募者を選択できる。expectedVersionで定員超過と同時更新を"
        "防ぎ、不一致・定員到達・選択不能状態は409。定員到達時は依頼をmatched、"
        "未選択応募をnot_selectedへ遷移する。"
    ),
    responses=api_errors(401, 403, 404, 409, 422, 500),
)
async def select_application(
    application_id: str,
    body: SelectionInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    try:
        return await repository.select_application(
            current_user,
            application_id,
            body.requestId,
            body.expectedVersion,
        )
    except MatchRepositoryError as error:
        runtime.raise_match_repository_error(error)


@router.get(
    "/matches/{match_id}",
    response_model=MatchResponse,
    tags=["Matches"],
    summary="マッチ詳細を取得",
    description="依頼者と選択された支援者本人だけが取得できる。",
    responses=api_errors(401, 403, 404, 500),
)
async def get_match(
    match_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    return await runtime.match_or_404(repository, current_user, match_id)


@router.get(
    "/matches/{match_id}/messages",
    response_model=MessageListResponse,
    tags=["Messages"],
    summary="チャット履歴を取得",
    description=(
        "成立したマッチの当事者だけが取得できる。送信日時の昇順。ブロックした相手の"
        "メッセージは除外する。nextCursorは次ページなしでnull（現行実装は常にnull）。"
    ),
    responses=api_errors(401, 403, 404, 500),
)
async def list_messages(
    match_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    await runtime.match_or_404(repository, current_user, match_id)
    try:
        items = await repository.list_messages(current_user, match_id)
    except MatchRepositoryError as error:
        runtime.raise_match_repository_error(error)
    return {"items": items, "nextCursor": None}


@router.post(
    "/matches/{match_id}/messages",
    response_model=MessageResponse,
    status_code=201,
    tags=["Messages"],
    summary="チャットメッセージを送信",
    description=(
        "マッチ当事者だけが送信できる。senderIdとsentAtはセッションとサーバー時刻から"
        "決定する。"
    ),
    responses=api_errors(401, 403, 404, 422, 500),
)
async def create_message(
    match_id: str,
    body: MessageInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    try:
        return await repository.create_message(
            current_user, match_id, body.body
        )
    except MatchRepositoryError as error:
        runtime.raise_match_repository_error(error)


@router.post(
    "/matches/{match_id}/complete",
    response_model=MatchResponse,
    tags=["Matches"],
    summary="活動完了を確認",
    description=(
        "依頼者と支援者本人だけが自分の役割で確認できる。片方のみは"
        "completion_pending、双方確認後はcompleted。重複確認、disputedまたは"
        "completedへの操作は409。"
    ),
    responses=api_errors(401, 403, 404, 409, 422, 500),
)
async def complete_match(
    match_id: str,
    body: CompletionInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    try:
        return await repository.complete(
            current_user, match_id, body.actorRole
        )
    except MatchRepositoryError as error:
        runtime.raise_match_repository_error(error)


@router.post(
    "/matches/{match_id}/dispute",
    response_model=MatchResponse,
    tags=["Matches"],
    summary="マッチングキャンセルを申告",
    description=(
        "当事者が理由を付けてマッチと依頼をdisputedへ遷移する。completedまたは既に"
        "disputedの場合は409。"
    ),
    responses=api_errors(401, 403, 404, 409, 422, 500),
)
async def dispute_match(
    match_id: str,
    body: DisputeInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    try:
        return await repository.dispute(current_user, match_id, body.reason)
    except MatchRepositoryError as error:
        runtime.raise_match_repository_error(error)
