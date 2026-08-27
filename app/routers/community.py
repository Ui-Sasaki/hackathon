"""Review, achievement, verification, and safety API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api_support import (
    api_errors,
    block_repository_dependency,
    match_repository_dependency,
    request_repository_dependency,
)
from app.auth import CurrentUser, get_current_user
from app.repositories.blocks import BlockRepository, BlockRepositoryError
from app.repositories.matches import MatchRepository
from app.repositories.requests import RequestRepository
from app.schemas import (
    AchievementInput,
    AchievementResponse,
    AchievementVisibilityInput,
    BlockInput,
    BlockResponse,
    ReportInput,
    ReportResponse,
    ReviewInput,
    ReviewResponse,
    VerificationInput,
    VerificationResponse,
)
from app.services.requests import require_request


router = APIRouter()


@router.post(
    "/matches/{match_id}/reviews",
    response_model=ReviewResponse,
    status_code=201,
    tags=["Reviews"],
    summary="完了した相手をレビュー",
    description=(
        "completedのマッチ当事者だけが相手へ1件投稿できる。未完了または重複投稿は409。"
    ),
    responses=api_errors(401, 403, 404, 409, 422, 500),
)
async def create_review(
    match_id: str,
    body: ReviewInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    match = await runtime.match_or_404(repository, current_user, match_id)
    actor_role = runtime.ensure_match_participant(match, current_user.user_id)
    if match["status"] != "completed":
        raise HTTPException(409, detail={"code": "MATCH_NOT_COMPLETED"})
    if any(
        review["matchId"] == match_id
        and review["reviewerId"] == current_user.user_id
        for review in runtime.reviews.values()
    ):
        raise HTTPException(409, detail={"code": "DUPLICATE_REVIEW"})
    item = {
        "id": runtime.new_id("review"),
        "matchId": match_id,
        "reviewerId": current_user.user_id,
        "revieweeId": (
            match["helperId"]
            if actor_role == "requester"
            else match["requesterId"]
        ),
        **body.model_dump(),
        "createdAt": runtime.now_iso(),
    }
    runtime.reviews[item["id"]] = item
    return item


@router.post(
    "/achievements/generate",
    response_model=AchievementResponse,
    status_code=201,
    tags=["Achievements"],
    summary="AI実績プロフィールを生成",
    description=(
        "completedのマッチ当事者だけが生成できる開発用AIモック。個人情報を含めず、"
        "公開には本人承認が必要。"
    ),
    responses=api_errors(401, 403, 404, 409, 422, 500),
)
async def generate_achievement(
    body: AchievementInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    match_repository: MatchRepository = Depends(match_repository_dependency),
):
    from app.cruds import main as runtime

    match = await runtime.match_or_404(
        match_repository, current_user, body.matchId
    )
    runtime.ensure_match_participant(match, current_user.user_id)
    if match["status"] != "completed":
        raise HTTPException(409, detail={"code": "MATCH_NOT_COMPLETED"})
    request_item = await require_request(
        repository, current_user, match["requestId"]
    )
    item = {
        "id": runtime.new_id("ach"),
        "userId": match["helperId"],
        "matchId": match["id"],
        "generatedText": (
            "地域住民の依頼に対応し、安全に配慮しながら支援活動を完了した。"
        ),
        "facts": {
            "category": request_item["category"],
            "minutes": request_item["estimatedMinutes"],
        },
        "visibility": body.visibility,
        "status": "generated",
        "modelName": "mock-model",
        "promptVersion": "mock-v1",
        "generatedAt": runtime.now_iso(),
        "approvedAt": None,
    }
    runtime.achievements[item["id"]] = item
    return item


@router.patch(
    "/achievements/visibility",
    response_model=AchievementResponse,
    tags=["Achievements"],
    summary="AI実績の公開範囲を更新",
    description=(
        "実績の対象本人だけが変更できる。public指定はapproved=trueによる本人承認が必須。"
    ),
    responses=api_errors(401, 403, 404, 409, 422, 500),
)
async def update_achievement_visibility(
    body: AchievementVisibilityInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    from app.cruds import main as runtime

    item = runtime.achievements.get(body.achievementId)
    if not item:
        raise HTTPException(404, detail={"code": "ACHIEVEMENT_NOT_FOUND"})
    if item["userId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if body.visibility == "public" and not body.approved:
        raise HTTPException(
            409, detail={"code": "ACHIEVEMENT_APPROVAL_REQUIRED"}
        )
    item["visibility"] = body.visibility
    if body.approved:
        item["approvedAt"] = runtime.now_iso()
        item["status"] = "approved"
    return item


@router.post(
    "/verifications",
    response_model=VerificationResponse,
    status_code=201,
    tags=["Verification"],
    summary="本人確認を申請",
    description=(
        "大学メールまたは学生証で申請する開発用モック。学生証方式は非公開ストレージ"
        "キーが必須だが、キーや画像はレスポンスに含めない。審査中の重複申請は409。"
    ),
    responses=api_errors(401, 409, 422, 500),
)
async def create_verification(
    body: VerificationInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    from app.cruds import main as runtime

    if body.method == "student_card" and not body.storageObjectKey:
        raise HTTPException(422, detail={"code": "STORAGE_OBJECT_REQUIRED"})
    if any(
        item["status"] == "pending"
        and item["userId"] == current_user.user_id
        for item in runtime.verifications.values()
    ):
        raise HTTPException(
            409, detail={"code": "VERIFICATION_ALREADY_PENDING"}
        )
    item = {
        "id": runtime.new_id("verification"),
        "userId": current_user.user_id,
        **body.model_dump(),
        "status": "pending",
        "createdAt": runtime.now_iso(),
    }
    runtime.verifications[item["id"]] = item
    runtime.users_store[current_user.user_id]["verificationStatus"] = "pending"
    return item


@router.post(
    "/reports",
    response_model=ReportResponse,
    status_code=201,
    tags=["Safety"],
    summary="違反・危険行為を通報",
    description=(
        "通報者はセッションから決定する。詐欺または危険作業の依頼通報はhighとなり、"
        "対象依頼をsuspendedへ自動遷移する。"
    ),
    responses=api_errors(401, 422, 500),
)
async def create_report(
    body: ReportInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    from app.cruds import main as runtime

    item = {
        "id": runtime.new_id("report"),
        "reporterId": current_user.user_id,
        **body.model_dump(),
        "severity": (
            "high" if body.reason in {"fraud", "dangerous_work"} else "medium"
        ),
        "status": "open",
        "createdAt": runtime.now_iso(),
    }
    runtime.reports[item["id"]] = item
    runtime.record_audit_event(
        actor_id=current_user.user_id,
        event_type="report_created",
        target_type=body.targetType,
        target_id=body.targetId,
        detail={"reportId": item["id"], "severity": item["severity"]},
    )
    if item["severity"] == "high" and body.targetType == "request":
        try:
            target_id = uuid.UUID(body.targetId)
        except ValueError:
            target_id = None
        if target_id is not None:
            await repository.set_status(
                current_user, str(target_id), "suspended"
            )
            runtime.record_audit_event(
                actor_id=current_user.user_id,
                event_type="request_auto_suspended",
                target_type="request",
                target_id=body.targetId,
                detail={"reportId": item["id"]},
            )
    return item


@router.post(
    "/users/{user_id}/block",
    response_model=BlockResponse,
    status_code=201,
    tags=["Safety"],
    summary="利用者をブロックまたは解除",
    description=(
        "blocked=trueでブロック、falseで解除する。セッション本人との関係として保存し、"
        "対象との依頼・応募・メッセージを非表示にする。自分自身は指定不可。"
    ),
    responses=api_errors(401, 404, 422, 500),
)
async def set_user_block(
    user_id: str,
    body: BlockInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: BlockRepository = Depends(block_repository_dependency),
):
    try:
        return await repository.set(current_user, user_id, body.blocked)
    except BlockRepositoryError as exc:
        status_code = 422 if exc.code == "SELF_BLOCK_NOT_ALLOWED" else 404
        raise HTTPException(status_code, detail={"code": exc.code}) from exc
