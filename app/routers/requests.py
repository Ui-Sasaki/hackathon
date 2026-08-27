"""Request creation, structure, search, and lifecycle API routes."""

from datetime import datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import ValidationError

from app.api_support import (
    api_errors,
    application_repository_dependency,
    request_repository_dependency,
)
from app.auth import CurrentUser, get_current_user
from app.repositories.applications import ApplicationRepository
from app.repositories.requests import (
    InvalidCursor,
    RequestRepository,
    decode_cursor,
    encode_cursor,
)
from app.schemas import (
    LocationResolveInput,
    MaskingConfirmationResponse,
    RequestInput,
    RequestListResponse,
    RequestResponse,
    RequestUpdateInput,
    StructureInput,
    StructuredRequestResponse,
)
from app.services.requests import cancel_owned_request, require_request, update_owned_request


router = APIRouter()
logger = logging.getLogger(__name__)


async def request_or_404(
    repository: RequestRepository,
    current_user: CurrentUser,
    request_id: str,
) -> dict[str, Any]:
    return await require_request(repository, current_user, request_id)


@router.post(
    "/requests/structure",
    response_model=StructuredRequestResponse | MaskingConfirmationResponse,
    tags=["Requests"],
    summary="依頼文を構造化",
    description=(
        "自由記述を依頼候補へ構造化する開発用AIモック。個人情報をマスクし、"
        "検出時は確認を求める。結果は自動公開されない。"
    ),
    responses=api_errors(401, 422, 500),
)
async def structure_request(
    body: StructureInput,
    _current_user: CurrentUser = Depends(get_current_user),
):
    from app.cruds import main as runtime

    masking = runtime.mask_request_text(body.text)
    if masking["hasDetections"] and not body.maskingConfirmed:
        runtime.masking_metrics["confirmationRequired"] += 1
        return {
            **masking,
            "status": "masking_confirmation_required",
            "requiresMaskingConfirmation": True,
            "message": "マスキング箇所を確認し、必要なら元の入力を修正してください",
        }
    if any(
        word in masking["maskedText"]
        for word in ["電気工事", "医療行為", "介護", "送迎"]
    ):
        raise HTTPException(
            422,
            detail={"code": "PROHIBITED_REQUEST", "riskLevel": "prohibited"},
        )
    try:
        result = await runtime.structure_llm_client(
            masking["maskedText"], body.areaCode
        )
    except Exception:
        logger.warning("Request structure service failed after masking")
        raise HTTPException(
            503, detail={"code": "STRUCTURE_SERVICE_UNAVAILABLE"}
        ) from None
    runtime.masking_metrics["submitted"] += 1
    return {
        **result,
        "masking": {
            "detections": masking["detections"],
            "ruleVersion": masking["ruleVersion"],
            "confirmed": body.maskingConfirmed,
        },
        "requiresConfirmation": True,
    }


@router.post(
    "/requests/masking-preview",
    tags=["Requests"],
    summary="LLM送信前のマスキング結果を確認",
)
async def preview_request_masking(
    body: StructureInput,
    _current_user: CurrentUser = Depends(get_current_user),
):
    from app.cruds import main as runtime

    runtime.masking_metrics["previewed"] += 1
    return runtime.mask_request_text(body.text)


@router.get(
    "/requests",
    response_model=RequestListResponse,
    tags=["Requests"],
    summary="公開依頼を検索",
    description=(
        "カテゴリ・日時・必要人数・概算距離・本人確認状態で絞り込み、カーソルページング"
        "で返す。現在地または登録地域による並び替え元もoriginで返す。"
    ),
    responses=api_errors(401, 422, 500),
)
async def list_requests(
    category: str | None = None,
    areaCode: str | None = None,
    scheduledFrom: datetime | None = None,
    scheduledTo: datetime | None = None,
    requiredHelpers: int | None = Query(default=None, ge=1, le=5),
    maxDistanceKm: float | None = Query(default=None, ge=0),
    verificationStatus: str | None = Query(
        default=None, pattern="^(unverified|pending|approved|rejected|expired)$"
    ),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    consentGranted: bool = False,
    locationFailure: str | None = Query(
        default=None, pattern="^(denied|timeout|unsupported|unavailable)$"
    ),
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    from app.cruds import main as runtime

    try:
        location = LocationResolveInput(
            consentGranted=consentGranted,
            latitude=latitude,
            longitude=longitude,
            failureReason=locationFailure,
        )
    except ValidationError:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR"}) from None
    origin_area_code, source = runtime.resolve_location(
        location, current_user, areaCode
    )
    try:
        request_cursor = decode_cursor(cursor) if cursor is not None else None
    except InvalidCursor as exc:
        raise HTTPException(422, detail={"code": "INVALID_CURSOR"}) from exc
    blocked_requester_ids = sorted(
        {
            second_user_id
            for first_user_id, second_user_id in runtime.blocks
            if first_user_id == current_user.user_id
        }
        | {
            first_user_id
            for first_user_id, second_user_id in runtime.blocks
            if second_user_id == current_user.user_id
        }
    )
    try:
        items = await repository.list(
            current_user,
            category=category,
            area_code=areaCode,
            limit=limit + 1,
            cursor=request_cursor,
            scheduled_from=scheduledFrom,
            scheduled_to=scheduledTo,
            required_helpers=requiredHelpers,
            max_distance_km=maxDistanceKm,
            verification_status=verificationStatus,
            blocked_requester_ids=blocked_requester_ids,
        )
    except InvalidCursor as exc:
        raise HTTPException(422, detail={"code": "INVALID_CURSOR"}) from exc
    has_more = len(items) > limit
    page = items[:limit]
    cursor_item = page[-1] if page else None
    if latitude is not None and longitude is not None:
        page.sort(
            key=lambda item: runtime.distance_km(
                latitude,
                longitude,
                runtime.REGIONS.get(
                    item["areaCode"], runtime.REGIONS["AREA-001"]
                ),
            )
        )
    else:
        page.sort(key=lambda item: item["areaCode"] != origin_area_code)
    next_cursor = encode_cursor(cursor_item) if has_more and cursor_item else None
    return {
        "items": page,
        "nextCursor": next_cursor,
        "origin": {"areaCode": origin_area_code, "source": source},
    }


@router.post(
    "/requests",
    response_model=RequestResponse,
    status_code=201,
    tags=["Requests"],
    summary="依頼を作成",
    description=(
        "認証済み本人を依頼者としてdraftを作成する。"
        "Idempotency-Keyが同じ再送は同じ結果を返す。"
    ),
    responses=api_errors(401, 422, 500),
)
async def create_request(
    body: RequestInput,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    from app.cruds import main as runtime

    cache_key = ("create_request", current_user.user_id, idempotency_key)
    if cache_key in runtime.idempotency_store:
        return runtime.idempotency_store[cache_key]
    area_code, _source = runtime.resolve_location(
        None, current_user, body.areaCode
    )
    item = await repository.create(
        current_user,
        {
            "title": body.title,
            "description": body.description,
            "category": body.category,
            "riskLevel": body.riskLevel,
            "areaCode": area_code,
            "scheduledAt": body.scheduledAt,
            "estimatedMinutes": body.estimatedMinutes,
            "requiredHelpers": body.requiredHelpers,
        },
    )
    runtime.idempotency_store[cache_key] = item
    return item


@router.get(
    "/requests/{request_id}",
    response_model=RequestResponse,
    tags=["Requests"],
    summary="依頼詳細を取得",
    description="閲覧可能な依頼を返す。ブロック関係など非表示対象は存在を伏せて404。",
    responses=api_errors(401, 404, 500),
)
async def get_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    from app.cruds import main as runtime

    item = await request_or_404(repository, current_user, request_id)
    if runtime.is_blocked_pair(current_user.user_id, item["requesterId"]):
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    return item


@router.patch(
    "/requests/{request_id}",
    response_model=RequestResponse,
    tags=["Requests"],
    summary="自分の依頼を更新",
    description=(
        "依頼者本人だけが更新可能。expectedVersion不一致や更新不能状態は409。"
    ),
    responses=api_errors(401, 403, 404, 409, 422, 500),
)
async def update_request(
    request_id: str,
    body: RequestUpdateInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    changes = body.model_dump(exclude={"expectedVersion"}, exclude_none=True)
    return await update_owned_request(
        repository,
        current_user,
        request_id,
        body.expectedVersion,
        changes,
    )


@router.delete(
    "/requests/{request_id}",
    status_code=204,
    tags=["Requests"],
    summary="自分の依頼を取消",
    description=(
        "依頼者本人が取消可能な状態の依頼をcancelledへ遷移させ、"
        "未処理応募もcancelledにする。レスポンス本文はない。"
    ),
    responses=api_errors(401, 403, 404, 409, 500),
)
async def cancel_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
):
    await cancel_owned_request(repository, current_user, request_id)
    await application_repository.cancel_pending_for_request(
        current_user, request_id
    )
    return None
