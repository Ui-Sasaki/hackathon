from copy import deepcopy
import base64
import binascii
from datetime import datetime, timezone
import json
import logging
import math
import os
import re
import uuid
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
import httpx
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.auth import (
    SUPERTOKENS_ENABLED, CurrentUser, configure_user_creator, configure_user_lookup,
    cors_headers, get_current_user,
)
from app.repositories.requests import (
    InvalidCursor, RequestRepository, decode_cursor, encode_cursor, get_request_repository,
)
from app.repositories.applications import (
    ApplicationRepository, get_application_repository,
)
from app.repositories.structure_audits import structure_audit_repository
from app.repositories.request_dismissals import (
    RequestDismissalRepository, get_request_dismissal_repository,
)
from app.repositories.saved_requests import (
    SavedRequestRepository, get_saved_request_repository,
)
from app.repositories.user_settings import (
    UserSettingsRepository, get_user_settings_repository,
)
from app.services.applications import (
    create_application as create_application_service,
    select_application as select_application_service,
    withdraw_application as withdraw_application_service,
)
from app.services.requests import cancel_owned_request, require_request, update_owned_request
from app.services import images
from app.repositories.uploads import (
    MemoryUploadRepository, UploadRepository, get_upload_repository,
)
from app.services import character, request_structuring, safety
if SUPERTOKENS_ENABLED:
    from supertokens_python.framework.fastapi import get_middleware
from app.routers import system_router
from app.settings import reject_unsafe_in_production, settings
from app.schemas import (
    AchievementInput, AchievementResponse, AchievementVisibilityInput,
    ApplicationInput, ApplicationListResponse, ApplicationResponse,
    CharacterProgressResponse,
    BlockInput, BlockResponse, CompletionInput, DisputeInput, ErrorResponse,
    LocationResolveInput, LocationResolveResponse, MatchResponse, MessageInput,
    MaskingConfirmationResponse, MessageListResponse, MessageResponse,
    ProfileResponse, ProfileUpdateInput,
    ReportInput, ReportResponse, RequestInput, RequestListResponse, RequestResponse,
    RequestUpdateInput, ResetResponse, ReviewInput, ReviewResponse, SelectionInput,
    SavedRequestListResponse,
    StructureInput, StructuredRequestResponse, VerificationInput, VerificationResponse,
    ProfileImageInput, ProfileImageResponse, UploadSessionInput, UploadSessionResponse,
    UploadedContentResponse,
    UserSettingsResponse, UserSettingsUpdateInput,
    RecommendedRequestListResponse,
)


app = FastAPI(
    title="たすけの輪 API",
    version="0.1.0",
    description=(
        "地域の依頼と支援者をつなぐAPI契約。業務APIはSuperTokensのHttpOnly Cookie"
        "セッションが必須で、ユーザーID・ロール・送信日時はサーバーが決定する。"
        "`/auth/*` はSuperTokensが提供する。依頼はRepositoryに保存されるが、応募以降、"
        "AI、本人確認は現在開発用インメモリ実装である。`/_mock/reset` は明示的に有効化"
        "した非本番環境だけで利用できる。"
    ),
)

class ApiPrefixMiddleware:
    """要件書の /api パスと、既存フロント用の無接頭辞パスを両方提供する。"""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (
            scope["path"] == "/api" or scope["path"].startswith("/api/")
        ):
            scope = dict(scope)
            scope["path"] = scope["path"][4:] or "/"
            scope["raw_path"] = scope["path"].encode()
        await self.asgi_app(scope, receive, send)


app.add_middleware(ApiPrefixMiddleware)
if SUPERTOKENS_ENABLED:
    app.add_middleware(get_middleware())
app.include_router(system_router)


ERROR_MESSAGES = {
    "BAD_REQUEST": "リクエストを処理できません",
    "AUTHENTICATION_REQUIRED": "認証が必要です",
    "USER_PROFILE_NOT_FOUND": "ユーザープロフィールが見つかりません",
    "USER_SUSPENDED": "利用停止中のユーザーです",
    "ROLE_FORBIDDEN": "この操作を行う権限がありません",
    "MFA_REQUIRED": "多要素認証が必要です",
    "REQUEST_NOT_FOUND": "依頼が見つかりません",
    "MATCH_NOT_FOUND": "マッチが見つかりません",
    "APPLICATION_NOT_FOUND": "応募が見つかりません",
    "REQUEST_STATE_CONFLICT": "依頼の状態が更新されているため処理できません",
    "INVALID_CURSOR": "カーソルが無効です",
    "VALIDATION_ERROR": "入力内容を確認してください",
    "REGION_SELECTION_REQUIRED": "地域を選択してください",
    "INTERNAL_SERVER_ERROR": "サーバー内部でエラーが発生しました",
}

STATUS_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_REQUIRED",
    403: "ROLE_FORBIDDEN",
    404: "NOT_FOUND",
    409: "STATE_CONFLICT",
    413: "IMAGE_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_SERVER_ERROR",
}


def api_errors(*statuses: int) -> dict[int, dict[str, Any]]:
    """OpenAPI error contracts, limited to errors reachable by each operation."""
    examples = {
        400: ("BAD_REQUEST", "リクエストを処理できません"),
        401: ("AUTHENTICATION_REQUIRED", "認証が必要です"),
        403: ("ROLE_FORBIDDEN", "この操作を行う権限がありません"),
        404: ("REQUEST_NOT_FOUND", "対象が見つかりません"),
        409: ("REQUEST_STATE_CONFLICT", "依頼の状態が更新されているため処理できません"),
        413: ("IMAGE_TOO_LARGE", "ファイルが大きすぎます"),
        415: ("UNSUPPORTED_MEDIA_TYPE", "対応していない形式です"),
        422: ("VALIDATION_ERROR", "入力内容を確認してください"),
        500: ("INTERNAL_SERVER_ERROR", "サーバー内部でエラーが発生しました"),
        502: ("STRUCTURE_INVALID_RESPONSE", "構造化サービスの応答を検証できません"),
        503: ("STRUCTURE_SERVICE_UNAVAILABLE", "構造化サービスを利用できません"),
    }
    return {
        status: {
            "model": ErrorResponse,
            "description": examples[status][1],
            "content": {"application/json": {"example": {"error": {
                "code": examples[status][0], "message": examples[status][1],
                "details": {}, "requestId": "trace_0123abcd",
            }}}},
        }
        for status in statuses
    }
logger = logging.getLogger(__name__)

MASKING_RULE_VERSION = "pii-mask-v1"
masking_metrics = {"previewed": 0, "confirmationRequired": 0, "submitted": 0}
PII_MASK_RULES = (
    ("email", "[メールアドレス]", re.compile(r"[A-Za-z0-9Ａ-Ｚａ-ｚ０-９._%+－-]+[@＠][A-Za-z0-9Ａ-Ｚａ-ｚ０-９.-]+[.．][A-Za-zＡ-Ｚａ-ｚ]{2,}")),
    ("phone", "[電話番号]", re.compile(r"(?<![0-9０-９])[0０][0-9０-９]{1,4}[-ー－―]?[0-9０-９]{1,4}[-ー－―]?[0-9０-９]{3,4}(?![0-9０-９])")),
    ("postal_code", "[郵便番号]", re.compile(r"〒?\s*[0-9０-９]{3}[-ー－―][0-9０-９]{4}")),
    ("certificate_number", "[証明書番号]", re.compile(r"(?:免許証|学生証|証明書)(?:番号|No[.．]?)?\s*[:：]?\s*[A-Za-zＡ-Ｚａ-ｚ0-9０-９-]{5,}")),
    ("address", "[詳細住所]", re.compile(r"(?:東京都|北海道|(?:京都|大阪)府|.{2,3}県).{1,20}(?:市|区|町|村).{1,30}(?:[0-9０-９]+(?:[-ー－―丁目番地号][0-9０-９]*)+|丁目)")),
    ("name", "[氏名]", re.compile(r"(?:氏名|名前)\s*(?:は|[:：])?\s*[一-龥々]{2,8}(?:\s|　)?[一-龥々]{1,8}")),
)


def mask_request_text(text: str) -> dict[str, Any]:
    masked_text = text
    detections = []
    for pii_type, placeholder, pattern in PII_MASK_RULES:
        masked_text, count = pattern.subn(placeholder, masked_text)
        if count:
            detections.append(
                {"type": pii_type, "placeholder": placeholder, "count": count}
            )
    return {
        "maskedText": masked_text,
        "detections": detections,
        "hasDetections": bool(detections),
        "ruleVersion": MASKING_RULE_VERSION,
    }


async def default_structure_llm_client(
    masked_text: str, _area_code: str | None
) -> dict[str, Any]:
    return await request_structuring.LocalStructureProvider().structure(
        masked_text, _area_code
    )


StructureLLMClient = Callable[[str, str | None], Awaitable[dict[str, Any]]]
class CallableStructureProvider:
    model = "configured-structure-client"

    def __init__(self, client: StructureLLMClient) -> None:
        self.client = client

    async def structure(self, text: str, area_code: str | None) -> dict[str, Any]:
        return await self.client(text, area_code)


structure_provider: request_structuring.StructureProvider = (
    request_structuring.configured_provider()
)


def configure_structure_llm_client(client: StructureLLMClient) -> None:
    global structure_provider
    structure_provider = CallableStructureProvider(client)


safety_llm_client: safety.SafetyLLMClient = safety.default_safety_llm_client


def configure_safety_llm_client(client: safety.SafetyLLMClient) -> None:
    global safety_llm_client
    safety_llm_client = client


def prohibited_request_error(assessment: safety.RiskAssessment) -> HTTPException:
    """禁止判定を、理由を伏せずに安全な形でクライアントへ返す。"""
    return HTTPException(422, detail={
        "code": "PROHIBITED_REQUEST",
        "riskLevel": assessment.level,
        "reasonCodes": list(assessment.reason_codes),
        "messages": list(assessment.messages),
        "ruleVersion": safety.RULE_VERSION,
    })

REGIONS = {
    "AREA-001": {"label": "大学周辺", "latitude": 43.062, "longitude": 141.354},
    "AREA-002": {"label": "大学北側", "latitude": 43.082, "longitude": 141.350},
    "AREA-003": {"label": "駅周辺", "latitude": 43.068, "longitude": 141.351},
}


def distance_km(latitude: float, longitude: float, region: dict[str, Any]) -> float:
    radius_km = 6371.0
    lat1, lat2 = math.radians(latitude), math.radians(region["latitude"])
    lat_delta = math.radians(region["latitude"] - latitude)
    lon_delta = math.radians(region["longitude"] - longitude)
    a = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(lon_delta / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_region(latitude: float, longitude: float) -> str:
    return min(
        REGIONS,
        key=lambda code: distance_km(latitude, longitude, REGIONS[code]),
    )


def resolve_location(
    location: LocationResolveInput | None,
    current_user: CurrentUser,
    selected_area_code: str | None = None,
) -> tuple[str, str]:
    if location and location.latitude is not None and location.longitude is not None:
        return nearest_region(location.latitude, location.longitude), "current_location"
    area_code = selected_area_code or users_store.get(current_user.user_id, {}).get(
        "areaCode"
    )
    if not area_code or area_code not in REGIONS:
        raise HTTPException(422, detail={"code": "REGION_SELECTION_REQUIRED"})
    source = "selected_region" if selected_area_code else "registered_region"
    return area_code, source


def request_id_for(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id or new_id("trace")


def error_body(
    code: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": ERROR_MESSAGES.get(code, code.replace("_", " ").lower()),
            "details": details or {},
            "requestId": request_id,
        }
    }


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = request_id_for(request)
    detail = dict(exc.detail) if isinstance(exc.detail, dict) else {}
    code = detail.pop("code", STATUS_ERROR_CODES.get(exc.status_code, "HTTP_ERROR"))
    # String exception details can contain framework internals or user data. Only
    # explicitly structured domain details are safe to expose.
    detail.pop("message", None)
    logger.warning(
        "API error requestId=%s method=%s path=%s status=%s code=%s",
        request_id, request.method, request.url.path, exc.status_code, code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, request_id, detail),
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    request_id = request_id_for(request)
    # Pydantic's raw errors include the rejected input. Keep only diagnostics so
    # passwords, descriptions, identity data, etc. cannot be reflected back.
    errors = [
        {"type": error["type"], "loc": list(error["loc"]), "msg": error["msg"]}
        for error in exc.errors()
    ]
    logger.warning(
        "API validation error requestId=%s method=%s path=%s errorCount=%s",
        request_id, request.method, request.url.path, len(errors),
    )
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            error_body("VALIDATION_ERROR", request_id, {"errors": errors})
        ),
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = request_id_for(request)
    logger.exception(
        "Unhandled API error requestId=%s method=%s path=%s",
        request_id, request.method, request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_SERVER_ERROR", request_id),
        headers={"X-Request-ID": request_id},
    )


class RequestIdMiddleware:
    """Attach one server-generated trace ID without buffering response bodies."""

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.asgi_app(scope, receive, send)
            return

        request_id = new_id("trace")
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        await self.asgi_app(scope, receive, send_with_request_id)


app.add_middleware(RequestIdMiddleware)
# CORS must be the outermost middleware so responses produced directly by
# SuperTokens (including refresh failures) receive the browser CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WEBSITE_DOMAIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=cors_headers(),
)


async def request_repository_dependency() -> RequestRepository:
    """Resolve the configured repository without a test-time threadpool hop."""
    return get_request_repository()


async def application_repository_dependency() -> ApplicationRepository:
    """Resolve the application repository without a test-time threadpool hop."""
    return get_application_repository()

async def user_settings_repository_dependency() -> UserSettingsRepository:
    return get_user_settings_repository()


async def request_dismissal_repository_dependency() -> RequestDismissalRepository:
    return get_request_dismissal_repository()


async def saved_request_repository_dependency() -> SavedRequestRepository:
    return get_saved_request_repository()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def get_or_404(store: dict, entity_id: str, error_code: str) -> dict:
    item = store.get(entity_id)
    if item is None:
        raise HTTPException(404, detail={"code": error_code})
    return item


# 依頼は Postgres へ永続化された（#4）。この2件は
# supabase/migrations/20260821000000_user_provisioning.sql の app.mock_reset_requests() が
# 作る種データの id と一致させてある。id は uuid5（namespace: NAMESPACE_URL,
# 'tetote:seed:req_1024' / 'tetote:seed:req_1025'）で再現可能に生成した。
SEED_REQUEST_1024 = "5fcfec7f-a8b0-58d4-931e-593d60355ee3"
SEED_REQUEST_1025 = "39521aee-fc9b-5be6-9652-b3cf45d9107f"

HELPERS = {
    "usr_207": {
        "id": "usr_207",
        "displayName": "田中 悠",
        "verificationStatus": "approved",
        "universityVerified": True,
        "skillTags": ["犬", "地域清掃"],
        "achievementCount": 12,
    },
    "usr_208": {
        "id": "usr_208",
        "displayName": "佐藤 海",
        "verificationStatus": "unverified",
        "universityVerified": True,
        "skillTags": ["ペット支援"],
        "achievementCount": 3,
    },
}

AREA_CENTERS = {
    "AREA-001": (35.6812, 139.7671),
}

PUBLIC_REQUEST_FIELDS = {
    "id", "requesterId", "title", "description", "category", "riskLevel",
    "areaCode", "areaLabel", "scheduledAt", "estimatedMinutes",
    "requiredHelpers", "acceptedHelpers", "status", "warnings", "createdAt",
}


def reset_store() -> None:
    global applications, matches, messages, reviews, achievements
    global profile_store, users_store, verifications, reports, blocks, audit_logs
    global idempotency_store
    profile_store = {
        "id": "usr_101",
        "displayName": "山田 花子",
        "role": "member",
        "emailVerified": True,
        "verificationStatus": "approved",
        "areaCode": "AREA-001",
        "status": "active",
    }
    users_store = {
        profile_store["id"]: profile_store,
        "usr_207": {
            **HELPERS["usr_207"], "role": "member", "status": "active",
            "emailVerified": True,
        },
        "usr_208": {
            **HELPERS["usr_208"], "role": "member", "status": "active",
            "emailVerified": True,
        },
        "usr_301": {
            "id": "usr_301", "displayName": "鈴木 雪", "role": "member",
            "status": "active", "emailVerified": True,
            "verificationStatus": "unverified", "areaCode": "AREA-001",
        },
    }
    applications = {
        "app_55": {
            "id": "app_55",
            "requestId": SEED_REQUEST_1024,
            "helperId": "usr_207",
            "message": "犬の散歩経験があります",
            "availableAt": "2026-08-19T17:00:00+09:00",
            "status": "applied",
            "createdAt": "2026-08-18T12:00:00+09:00",
        },
        "app_56": {
            "id": "app_56",
            "requestId": SEED_REQUEST_1024,
            "helperId": "usr_208",
            "message": "18時以降なら対応できます",
            "availableAt": "2026-08-19T18:00:00+09:00",
            "status": "applied",
            "createdAt": "2026-08-18T12:10:00+09:00",
        },
    }
    matches = {}
    messages = {}
    reviews = {}
    achievements = {}
    verifications = {}
    reports = {}
    blocks = set()
    audit_logs = []
    idempotency_store = {}


reset_store()
configure_user_lookup(lambda user_id: users_store.get(user_id))


def create_user_profile(user_id: str) -> None:
    """Create the application-side profile linked to a SuperTokens user."""

    users_store.setdefault(
        user_id,
        {
            "id": user_id,
            "displayName": "",
            "role": "member",
            "status": "active",
            "emailVerified": False,
            "verificationStatus": "unverified",
        },
    )


configure_user_creator(create_user_profile)
def match_or_404(match_id: str) -> dict:
    return get_or_404(matches, match_id, "MATCH_NOT_FOUND")


def ensure_match_participant(match: dict, user_id: str) -> str:
    if match["requesterId"] == user_id:
        return "requester"
    if match["helperId"] == user_id:
        return "helper"
    raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})


def is_blocked_pair(first_user_id: str, second_user_id: str) -> bool:
    """Return whether either user has blocked the other."""

    return (
        (first_user_id, second_user_id) in blocks
        or (second_user_id, first_user_id) in blocks
    )


def record_audit_event(
    *,
    actor_id: str,
    event_type: str,
    target_type: str,
    target_id: str,
    result: str = "success",
    detail: dict[str, Any] | None = None,
) -> None:
    """Append an immutable mock audit event without recording request content."""

    audit_logs.append(
        {
            "id": new_id("audit"),
            "actorId": actor_id,
            "eventType": event_type,
            "targetType": target_type,
            "targetId": target_id,
            "result": result,
            "detail": detail or {},
            "createdAt": now_iso(),
        }
    )


# モックデータの初期化は開発・テスト専用の操作である。明示的に有効化した環境
# 以外では、存在自体を伏せたまま拒否する。
MOCK_RESET_ENABLED = os.getenv("MOCK_RESET_ENABLED", "false").lower() in {
    "1", "true", "yes", "on",
}

# 全データを初期状態へ戻す操作なので、本番では有効化させない。
reject_unsafe_in_production(
    "MOCK_RESET_ENABLED", MOCK_RESET_ENABLED, settings.environment
)


async def require_mock_environment() -> None:
    if not MOCK_RESET_ENABLED:
        raise HTTPException(404, detail={"code": "NOT_FOUND"})


@app.post("/_mock/reset", response_model=ResetResponse, tags=["Development mock"], summary="開発用モックデータを初期化", description="MOCK_RESET_ENABLED=trueの非本番環境だけで、認証済み利用者が実行できる。本番ではこの設定自体が起動時に拒否される。全モックデータを初期状態へ戻す。", responses=api_errors(401, 404, 500))
async def reset_mock(
    _: None = Depends(require_mock_environment),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
    user_settings_repository: UserSettingsRepository = Depends(
        user_settings_repository_dependency
    ),
    request_dismissal_repository: RequestDismissalRepository = Depends(
        request_dismissal_repository_dependency
    ),
    saved_request_repository: SavedRequestRepository = Depends(
        saved_request_repository_dependency
    ),
):
    reset_store()
    await repository.reset()
    await application_repository.reset()
    await get_upload_repository().reset()
    await structure_audit_repository.reset()
    await user_settings_repository.reset()
    await request_dismissal_repository.reset()
    await saved_request_repository.reset()
    return {"reset": True}


@app.get("/profile", response_model=ProfileResponse, tags=["Profile"], summary="自分のプロフィールを取得", description="Cookieセッションの本人の公開可能なプロフィールだけを返す。", responses=api_errors(401, 403, 500))
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    return users_store[current_user.user_id]


@app.patch("/profile", response_model=ProfileResponse, tags=["Profile"], summary="自分のプロフィールを更新", description="既存プロフィール画面の編集項目を更新する。ユーザーID、ロール、本人確認状態は入力できない。端末ローカルの画像URIは受け付けない。", responses=api_errors(401, 403, 422, 500))
async def update_profile(
    body: ProfileUpdateInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, detail={"code": "NO_CHANGES"})
    profile = users_store[current_user.user_id]
    candidate = {**profile, **changes}
    if candidate.get("helperType") == "student" and not all(
        candidate.get(field) for field in ("university", "faculty", "schoolYear")
    ):
        raise HTTPException(422, detail={"code": "STUDENT_PROFILE_INCOMPLETE"})
    if candidate.get("helperType") == "worker" and not candidate.get("occupation"):
        raise HTTPException(422, detail={"code": "WORKER_PROFILE_INCOMPLETE"})
    profile.update(changes)
    profile["updatedAt"] = now_iso()
    return profile


def upload_repository_dependency() -> UploadRepository:
    return get_upload_repository()


def image_error(error: images.ImageValidationError) -> HTTPException:
    return HTTPException(
        error.status, detail={"code": error.code, "message": error.message}
    )


def profile_image_url(view_token: str) -> str:
    return f"/profile/images/{view_token}"


async def owned_stored_upload(
    repository: UploadRepository, upload_id: str, current_user: CurrentUser,
    purpose: str,
) -> dict:
    """本人の、本文送信済みで期限内のアップロードだけを通す。"""
    session = await repository.get_session(upload_id)
    # 他人のアップロードは存在を伏せる。IDの総当たりで有無を知られないようにする。
    if session is None or session["ownerId"] != current_user.user_id:
        raise HTTPException(404, detail={"code": "UPLOAD_NOT_FOUND"})
    if session["purpose"] != purpose:
        raise HTTPException(422, detail={"code": "UPLOAD_PURPOSE_MISMATCH"})
    if session["status"] == "consumed":
        raise HTTPException(409, detail={"code": "UPLOAD_ALREADY_USED"})
    if session["status"] != "stored":
        raise HTTPException(409, detail={"code": "UPLOAD_CONTENT_MISSING"})
    if upload_expired(session):
        raise HTTPException(409, detail={"code": "UPLOAD_EXPIRED"})
    return session


def upload_expired(session: dict) -> bool:
    expires_at = datetime.fromisoformat(session["expiresAt"].replace("Z", "+00:00"))
    return expires_at <= datetime.now(timezone.utc)


@app.post("/uploads", response_model=UploadSessionResponse, status_code=201, tags=["Uploads"], summary="画像アップロードを開始", description="申告されたMIME type、拡張子、サイズを検証し、期限付きのアップロード先を発行する。ストレージ内部キーは返さない。", responses=api_errors(401, 413, 415, 422, 500))
async def create_upload_session(
    body: UploadSessionInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: UploadRepository = Depends(upload_repository_dependency),
):
    try:
        images.validate_declaration(body.contentType, body.byteSize, body.fileName)
    except images.ImageValidationError as error:
        raise image_error(error)
    # 開始のたびに、期限切れの未確定アップロードを回収する。
    await repository.purge_expired()
    session = await repository.create_session(
        current_user.user_id, body.purpose, body.contentType, body.byteSize
    )
    return {
        "uploadId": session["id"],
        "uploadUrl": f"/uploads/{session['id']}/content",
        "expiresAt": session["expiresAt"],
        "maxBytes": images.MAX_IMAGE_BYTES,
    }


@app.put("/uploads/{upload_id}/content", response_model=UploadedContentResponse, tags=["Uploads"], summary="画像の本文を送信", description="バイト列の実体から形式を判定し、申告と一致しない画像を拒否する。保存前にメタデータを除去する。", responses=api_errors(401, 404, 409, 413, 415, 422, 500))
async def upload_content(
    upload_id: str,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    repository: UploadRepository = Depends(upload_repository_dependency),
):
    session = await repository.get_session(upload_id)
    if session is None or session["ownerId"] != current_user.user_id:
        raise HTTPException(404, detail={"code": "UPLOAD_NOT_FOUND"})
    if session["status"] != "pending":
        raise HTTPException(409, detail={"code": "UPLOAD_ALREADY_COMPLETED"})
    if upload_expired(session):
        raise HTTPException(409, detail={"code": "UPLOAD_EXPIRED"})
    try:
        sanitized, content_type = images.sanitize_image(
            await request.body(), session["contentType"]
        )
    except images.ImageValidationError as error:
        raise image_error(error)
    stored = await repository.attach_content(upload_id, sanitized, content_type)
    return {
        "uploadId": stored["id"],
        "status": "stored",
        "contentType": stored["contentType"],
        "byteSize": stored["byteSize"],
    }


@app.put("/profile/image", response_model=ProfileImageResponse, tags=["Profile"], summary="プロフィール画像を確定", description="検証済みのアップロードを自分のプロフィール画像として確定する。確定に失敗した場合、既存の画像は残る。", responses=api_errors(401, 404, 409, 422, 500))
async def set_profile_image(
    body: ProfileImageInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: UploadRepository = Depends(upload_repository_dependency),
):
    await owned_stored_upload(
        repository, body.uploadId, current_user, "profile_image"
    )
    image = await repository.promote_to_image(body.uploadId, current_user.user_id)
    if image is None:
        raise HTTPException(409, detail={"code": "UPLOAD_CONTENT_MISSING"})
    profile = users_store[current_user.user_id]
    # 新しい画像を確定できてから、古い画像を消す。差し替え失敗で無画像にしない。
    previous_image_id = profile.get("imageId")
    profile["imageId"] = image["id"]
    profile["imageUrl"] = profile_image_url(image["viewToken"])
    profile["updatedAt"] = now_iso()
    if previous_image_id:
        await repository.delete_image(previous_image_id)
    return {
        "imageId": image["id"],
        "imageUrl": profile["imageUrl"],
        "updatedAt": profile["updatedAt"],
    }


@app.delete("/profile/image", status_code=204, tags=["Profile"], summary="プロフィール画像を削除", description="自分のプロフィール画像を削除する。設定していない場合は404。", responses=api_errors(401, 404, 500))
async def delete_profile_image(
    current_user: CurrentUser = Depends(get_current_user),
    repository: UploadRepository = Depends(upload_repository_dependency),
):
    profile = users_store[current_user.user_id]
    image_id = profile.get("imageId")
    if not image_id:
        raise HTTPException(404, detail={"code": "PROFILE_IMAGE_NOT_FOUND"})
    await repository.delete_image(image_id)
    profile["imageId"] = None
    profile["imageUrl"] = None
    profile["updatedAt"] = now_iso()
    return Response(status_code=204)


@app.get("/profile/images/{image_token}", tags=["Profile"], summary="プロフィール画像を取得", description="推測できない参照子で画像を返す。認証済み利用者だけが取得でき、キャッシュへ残さない。", responses=api_errors(401, 404, 500))
async def get_profile_image(
    image_token: str,
    _current_user: CurrentUser = Depends(get_current_user),
    repository: UploadRepository = Depends(upload_repository_dependency),
):
    image = await repository.find_image_by_token(image_token)
    # 本人確認書類はこの経路では出さない。プロフィール画像だけを配信する。
    if image is None or image["purpose"] != "profile_image":
        raise HTTPException(404, detail={"code": "PROFILE_IMAGE_NOT_FOUND"})
    return Response(
        content=image["data"],
        media_type=image["contentType"],
        headers={"Cache-Control": "private, no-store"},
    )
@app.get("/settings", response_model=UserSettingsResponse, tags=["Settings"], summary="自分の利用者設定を取得", description="Cookieセッション本人の通知、位置情報利用、文字サイズ設定だけを返す。通知設定はブラウザ・OSの通知権限を変更しない。", responses=api_errors(401, 500))
async def get_user_settings(
    current_user: CurrentUser = Depends(get_current_user),
    repository: UserSettingsRepository = Depends(user_settings_repository_dependency),
):
    return await repository.get(current_user)


@app.patch("/settings", response_model=UserSettingsResponse, tags=["Settings"], summary="自分の利用者設定を部分更新", description="指定した項目だけを更新する。locationEnabled=falseの場合、クライアントはブラウザ位置情報の取得を開始しない。notificationsEnabledはアプリ内の希望設定であり、ブラウザ・OS権限とは別に扱う。", responses=api_errors(401, 422, 500))
async def update_user_settings(
    body: UserSettingsUpdateInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: UserSettingsRepository = Depends(user_settings_repository_dependency),
):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, detail={"code": "NO_CHANGES"})
    return await repository.update(current_user, changes)


@app.post("/locations/resolve", response_model=LocationResolveResponse, tags=["Locations"], summary="現在地を概算地域へ変換", description="同意済み座標を概算地域へ変換する。座標は保存も返却もしない。取得失敗時は登録地域へフォールバックする。", responses=api_errors(401, 422, 500))
async def resolve_browser_location(
    body: LocationResolveInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    area_code, source = resolve_location(body, current_user)
    return {
        "areaCode": area_code,
        "areaLabel": REGIONS[area_code]["label"],
        "source": source,
        "fallbackUsed": source == "registered_region",
    }


@app.post("/requests/structure", response_model=StructuredRequestResponse | MaskingConfirmationResponse, tags=["Requests"], summary="依頼文を構造化", description="自由記述を検証済みの確認用下書きへ構造化する。個人情報をマスクし、検出時は確認を求める。結果は自動公開されない。", responses=api_errors(401, 422, 500, 502, 503))
async def structure_request(
    body: StructureInput,
    _current_user: CurrentUser = Depends(get_current_user),
):
    masking = mask_request_text(body.text)
    if masking["hasDetections"] and not body.maskingConfirmed:
        masking_metrics["confirmationRequired"] += 1
        return {
            **masking,
            "status": "masking_confirmation_required",
            "requiresMaskingConfirmation": True,
            "message": "マスキング箇所を確認し、必要なら元の入力を修正してください",
        }
    # LLMへ渡すのはマスク済みテキストだけ。危険度判定も同じ文字列だけを見る。
    assessment = await safety.assess_risk(
        masking["maskedText"], llm_client=safety_llm_client
    )
    if assessment.rejected:
        raise prohibited_request_error(assessment)
    try:
        result = await request_structuring.structure_request(
            masking["maskedText"], body.areaCode, structure_provider,
            structure_audit_repository,
        )
    except httpx.TimeoutException:
        logger.warning("Request structure provider timed out")
        raise HTTPException(503, detail={"code": "STRUCTURE_SERVICE_TIMEOUT"})
    except (httpx.HTTPStatusError, request_structuring.InvalidStructureResponse):
        logger.warning("Request structure provider returned an invalid response")
        raise HTTPException(502, detail={"code": "STRUCTURE_INVALID_RESPONSE"})
    except Exception:
        logger.warning("Request structure service failed after masking")
        raise HTTPException(503, detail={"code": "STRUCTURE_SERVICE_UNAVAILABLE"})
    masking_metrics["submitted"] += 1
    return {
        **result,
        "request": {
            "task": masking["maskedText"],
            "location": result.get("approximateArea"),
            "duration": (
                str(result["estimatedMinutes"])
                if result.get("estimatedMinutes") is not None else None
            ),
            "deadline": result.get("scheduledAt"),
            "notes": None,
        },
        "masking": {
            "detections": masking["detections"],
            "ruleVersion": masking["ruleVersion"],
            "confirmed": body.maskingConfirmed,
        },
        "safety": assessment.to_payload(),
    }


@app.post("/requests/masking-preview", tags=["Requests"], summary="LLM送信前のマスキング結果を確認")
async def preview_request_masking(
    body: StructureInput,
    _current_user: CurrentUser = Depends(get_current_user),
):
    masking_metrics["previewed"] += 1
    return mask_request_text(body.text)


async def request_or_404(
    repository: RequestRepository, current_user: CurrentUser, request_id: str,
) -> dict:
    return await require_request(repository, current_user, request_id)

def calculate_recommendation_score(
    request_item: dict[str, Any],
    helper_profile: dict[str, Any],
    distance_km_val: float | None,
) -> tuple[int, str]:
    """支援者と依頼の相性を100点満点で採点し、推薦理由を生成する"""
    score = 0
    reasons = []

    # 1. 距離スコア (最大40点)
    if distance_km_val is not None:
        if distance_km_val <= 1.0:
            score += 40
            reasons.append("現在地からとても近い")
        elif distance_km_val <= 3.0:
            score += 30
            reasons.append("現在地から近い")
        elif distance_km_val <= 5.0:
            score += 20
    else:
        # 位置情報が取れない場合は登録エリア一致を評価
        if request_item.get("areaCode") == helper_profile.get("areaCode"):
            score += 20
            reasons.append("登録エリア内")

    # 2. スキル・カテゴリ一致 (最大30点)
    category = request_item.get("category", "")
    skill_tags = helper_profile.get("skillTags", [])
    if category and category in skill_tags:
        score += 30
        reasons.append(f"あなたの得意な「{category}」")

    # 3. 信頼性・実績ボーナス (最大15点)
    achievement_count = helper_profile.get("achievementCount", 0)
    risk_level = request_item.get("riskLevel", "low")
    if risk_level == "medium" and achievement_count >= 5:
        score += 15
        reasons.append("あなたの豊富な実績が活かせる")
    elif risk_level == "low":
        score += 10

    # 4. 緊急度・時間スコア (最大15点)
    try:
        scheduled_at = datetime.fromisoformat(request_item["scheduledAt"].replace("Z", "+00:00"))
        hours_until = (scheduled_at - datetime.now(timezone.utc)).total_seconds() / 3600
        if 0 < hours_until <= 24:
            score += 15
            reasons.append("急募で助けを必要としている")
        elif 0 < hours_until <= 48:
            score += 10
        else:
            score += 5
    except (KeyError, ValueError):
        pass

    # 推薦理由の自然言語化
    if score >= 70 and len(reasons) >= 2:
        reason_text = f"{reasons[0]}、{reasons[1]}おすすめの依頼です。"
    elif reasons:
        reason_text = f"{reasons[0]}依頼です。"
    else:
        # 新規ユーザー・条件不一致時のフォールバック
        reason_text = "新着の支援募集です。"

    return min(score, 100), reason_text

@app.get("/requests/recommended", response_model=RecommendedRequestListResponse, tags=["Requests"], summary="パーソナライズされた依頼推薦", description="支援者のプロフィールに基づき、応募可能な依頼をスコアリングして推薦順に返す。")
async def get_recommended_requests(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    consentGranted: bool = False,
    locationFailure: str | None = Query(default=None, pattern="^(denied|timeout|unsupported|unavailable)$"),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    # 1. ユーザー情報と位置情報の取得
    helper_profile = users_store.get(current_user.user_id, {})
    is_verified = helper_profile.get("verificationStatus") == "approved"

    try:
        location = LocationResolveInput(
            consentGranted=consentGranted, latitude=latitude, longitude=longitude, failureReason=locationFailure
        )
    except ValidationError:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR"}) from None

    # 位置情報から距離計算の基準を取得
    origin_area_code, _source = resolve_location(location, current_user)

    # 2. ブロック関係の取得
    blocked_requester_ids = sorted(
        {second for first, second in blocks if first == current_user.user_id} |
        {first for first, second in blocks if second == current_user.user_id}
    )

    # 3. 候補データの抽出（推薦母集団として多めに取得）
    candidates = await repository.list(
        current_user,
        category=None,
        area_code=None,
        limit=100,
        blocked_requester_ids=blocked_requester_ids
    )

    scored_items = []
    for item in candidates:
        # === 必須除外フィルター（完了要件の適用） ===
        # 自分の依頼を除外
        if item["requesterId"] == current_user.user_id:
            continue
        # 募集終了、停止、期限切れの除外 (公開中の 'published' 以外は弾く)
        if item["status"] != "published":
            continue
        # 本人確認条件を満たさない依頼を除外（リスクMedium以上は確認済み必須とする業務ルール）
        if item.get("riskLevel") == "medium" and not is_verified:
            continue

        # === スコアリングと推薦理由の生成 ===
        dist_km = None
        if latitude is not None and longitude is not None and item.get("areaCode") in REGIONS:
            dist_km = distance_km(latitude, longitude, REGIONS[item["areaCode"]])

        score, reason = calculate_recommendation_score(item, helper_profile, dist_km)

        # 戻り値オブジェクトの構築
        scored_items.append({
            "request": item,
            "score": score,
            "reason": reason
        })

    # 4. ソートとページング
    # スコアの降順、同点の場合は作成日時の新しい順に並び替え
    scored_items.sort(key=lambda x: (x["score"], x["request"]["createdAt"]), reverse=True)

    page = scored_items[:limit]
    has_more = len(scored_items) > limit

    # モックとしての簡易的な次ページ判定（実運用では末尾要素のスコアやIDをエンコードして使用）
    next_cursor = "next_page_available" if has_more else None

    return {
        "items": page,
        "nextCursor": next_cursor
    }

@app.get("/requests", response_model=RequestListResponse, tags=["Requests"], summary="公開依頼を検索", description="カテゴリ・日時・必要人数・概算距離・本人確認状態で絞り込み、カーソルページングで返す。現在地または登録地域による並び替え元もoriginで返す。", responses=api_errors(401, 422, 500))
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
    dismissal_repository: RequestDismissalRepository = Depends(
        request_dismissal_repository_dependency
    ),
):
    try:
        location = LocationResolveInput(
            consentGranted=consentGranted,
            latitude=latitude,
            longitude=longitude,
            failureReason=locationFailure,
        )
    except ValidationError:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR"}) from None
    origin_area_code, source = resolve_location(location, current_user, areaCode)
    try:
        request_cursor = decode_cursor(cursor) if cursor is not None else None
    except InvalidCursor as exc:
        raise HTTPException(422, detail={"code": "INVALID_CURSOR"}) from exc
    blocked_requester_ids = sorted(
        {
            second_user_id
            for first_user_id, second_user_id in blocks
            if first_user_id == current_user.user_id
        }
        | {
            first_user_id
            for first_user_id, second_user_id in blocks
            if second_user_id == current_user.user_id
        }
    )
    dismissed_ids = await dismissal_repository.list_ids(current_user)
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
    items = [item for item in items if item["id"] not in dismissed_ids]
    has_more = len(items) > limit
    page = items[:limit]
    cursor_item = page[-1] if page else None
    if latitude is not None and longitude is not None:
        page.sort(
            key=lambda item: distance_km(
                latitude, longitude, REGIONS.get(item["areaCode"], REGIONS["AREA-001"])
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


@app.post("/requests", response_model=RequestResponse, status_code=201, tags=["Requests"], summary="依頼を作成", description="認証済み本人を依頼者としてdraftを作成する。Idempotency-Keyが同じ再送は同じ結果を返す。", responses=api_errors(401, 422, 500))
async def create_request(
    body: RequestInput,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    cache_key = ("create_request", current_user.user_id, idempotency_key)
    if cache_key in idempotency_store:
        return idempotency_store[cache_key]
    area_code, _source = resolve_location(None, current_user, body.areaCode)
    # 危険度はサーバー側で判定する。クライアントが送る riskLevel は採用しない。
    masked = mask_request_text(f"{body.title} {body.description}")
    assessment = await safety.assess_risk(
        masked["maskedText"],
        llm_client=safety_llm_client,
        scheduled_at=body.scheduledAt,
    )
    if assessment.rejected:
        raise prohibited_request_error(assessment)
    item = await repository.create(current_user, {
        "title": body.title, "description": body.description, "category": body.category,
        "riskLevel": assessment.level, "areaCode": area_code,
        "scheduledAt": body.scheduledAt, "estimatedMinutes": body.estimatedMinutes,
        "requiredHelpers": body.requiredHelpers,
    })
    # 判断不能と審査対象は公開せず、管理者審査へ送る。
    if assessment.needs_review and await repository.set_status(
        current_user, item["id"], "pending_review",
        expected_version=item["version"], bump_version=False,
    ):
        item = {**item, "status": "pending_review"}
    if assessment.messages:
        item = {**item, "warnings": list(assessment.messages)}
    idempotency_store[cache_key] = item
    return item


async def require_dismissible_request(
    request_id: str, current_user: CurrentUser, repository: RequestRepository,
) -> None:
    item = await request_or_404(repository, current_user, request_id)
    if (
        item["status"] != "published"
        or is_blocked_pair(current_user.user_id, item["requesterId"])
    ):
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})


async def require_public_request(
    request_id: str, current_user: CurrentUser, repository: RequestRepository,
) -> dict:
    item = await request_or_404(repository, current_user, request_id)
    if (
        item["status"] != "published"
        or is_blocked_pair(current_user.user_id, item["requesterId"])
    ):
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    return item


@app.get("/saved-requests", response_model=SavedRequestListResponse, tags=["Saved requests"], summary="保存した依頼を一覧", description="セッション本人が保存した公開中かつ閲覧可能な依頼だけを返す。", responses=api_errors(401, 500))
async def list_saved_requests(
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    saved_repository: SavedRequestRepository = Depends(
        saved_request_repository_dependency
    ),
):
    items = []
    for request_id in await saved_repository.list_ids(current_user):
        item = await repository.get(current_user, request_id)
        if (
            item is not None
            and item["status"] == "published"
            and not is_blocked_pair(current_user.user_id, item["requesterId"])
        ):
            items.append(item)
    items.sort(key=lambda item: (item["createdAt"], item["id"]), reverse=True)
    return {"items": items}


@app.post("/saved-requests/{request_id}", status_code=204, tags=["Saved requests"], summary="依頼を保存", description="閲覧可能な公開依頼をセッション本人の保存一覧へ冪等に追加する。", responses=api_errors(401, 404, 422, 500))
async def save_request(
    request_id: str = Path(min_length=1, max_length=100),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    saved_repository: SavedRequestRepository = Depends(
        saved_request_repository_dependency
    ),
) -> None:
    await require_public_request(request_id, current_user, repository)
    await saved_repository.save(current_user, request_id)


@app.delete("/saved-requests/{request_id}", status_code=204, tags=["Saved requests"], summary="依頼の保存を解除", description="閲覧可能な公開依頼をセッション本人の保存一覧から冪等に削除する。", responses=api_errors(401, 404, 422, 500))
async def remove_saved_request(
    request_id: str = Path(min_length=1, max_length=100),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    saved_repository: SavedRequestRepository = Depends(
        saved_request_repository_dependency
    ),
) -> None:
    await require_public_request(request_id, current_user, repository)
    await saved_repository.remove(current_user, request_id)


@app.post("/requests/{request_id}/dismiss", status_code=204, tags=["Requests"], summary="依頼を自分の一覧から非表示", description="セッション本人の非表示関係を冪等に保存する。他利用者の一覧には影響しない。", responses=api_errors(401, 404, 500))
async def dismiss_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    dismissal_repository: RequestDismissalRepository = Depends(
        request_dismissal_repository_dependency
    ),
) -> None:
    await require_dismissible_request(request_id, current_user, repository)
    await dismissal_repository.dismiss(current_user, request_id)


@app.delete("/requests/{request_id}/dismiss", status_code=204, tags=["Requests"], summary="依頼の非表示を解除", description="セッション本人の非表示関係を冪等に解除する。", responses=api_errors(401, 404, 500))
async def restore_dismissed_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    dismissal_repository: RequestDismissalRepository = Depends(
        request_dismissal_repository_dependency
    ),
) -> None:
    await require_dismissible_request(request_id, current_user, repository)
    await dismissal_repository.restore(current_user, request_id)


# #20: このエンドポイントは元々認証を要求せず、依頼の状態も検査していなかった。
# RLS は未認証アクター（app.actor_id 未設定）に一律 deny を返すため、Postgres へ
# 接続した時点で認証必須が構造として強制される。get_current_user() が無効な
# セッションを 401 で弾き、RLS が届かない行を 404 として隠す。
@app.get("/requests/{request_id}", response_model=RequestResponse, tags=["Requests"], summary="依頼詳細を取得", description="閲覧可能な依頼を返す。ブロック関係など非表示対象は存在を伏せて404。", responses=api_errors(401, 404, 500))
async def get_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    item = await request_or_404(repository, current_user, request_id)
    if is_blocked_pair(current_user.user_id, item["requesterId"]):
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    return item


@app.patch("/requests/{request_id}", response_model=RequestResponse, tags=["Requests"], summary="自分の依頼を更新", description="依頼者本人だけが更新可能。expectedVersion不一致や更新不能状態は409。", responses=api_errors(401, 403, 404, 409, 422, 500))
async def update_request(
    request_id: str,
    body: RequestUpdateInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    changes = body.model_dump(exclude={"expectedVersion"}, exclude_none=True)
    # 作成時の判定を更新で迂回できないよう、本文と日時が変わるなら judge し直す。
    if {"title", "description", "scheduledAt"} & changes.keys():
        current = await require_request(repository, current_user, request_id)
        # 他人の依頼で判定を走らせないための先出し確認。更新可否は下の Service が改めて判断する。
        if current["requesterId"] != current_user.user_id:
            raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
        masked = mask_request_text(
            f"{changes.get('title', current['title'])} "
            f"{changes.get('description', current['description'])}"
        )
        assessment = await safety.assess_risk(
            masked["maskedText"],
            llm_client=safety_llm_client,
            scheduled_at=changes.get("scheduledAt", current["scheduledAt"]),
        )
        if assessment.rejected:
            raise prohibited_request_error(assessment)
        # 保存済み riskLevel はここでは書き換えない。Postgres の update_request が
        # この列を受け取らず、Memory実装とだけ差が出るためである（COORD-003）。
        # 公開可否は status で止めるため、審査への遷移は下で行う。
    else:
        assessment = None
    item = await update_owned_request(
        repository, current_user, request_id, body.expectedVersion, changes,
    )
    if assessment is not None and assessment.needs_review and await repository.set_status(
        current_user, item["id"], "pending_review",
        expected_version=item["version"], bump_version=False,
    ):
        item = {**item, "status": "pending_review"}
    if assessment is not None and assessment.messages:
        item = {**item, "warnings": list(assessment.messages)}
    return item


@app.delete("/requests/{request_id}", status_code=204, tags=["Requests"], summary="自分の依頼を取消", description="依頼者本人が取消可能な状態の依頼をcancelledへ遷移させ、未処理応募もcancelledにする。レスポンス本文はない。", responses=api_errors(401, 403, 404, 409, 500))
async def cancel_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    await cancel_owned_request(repository, current_user, request_id)
    for application in applications.values():
        if application["requestId"] == request_id and application["status"] == "applied":
            application["status"] = "cancelled"
    return None


@app.get("/requests/{request_id}/applications", response_model=ApplicationListResponse, tags=["Applications"], summary="自分の依頼の応募者を一覧", description="依頼者本人だけが閲覧でき、ブロック関係の応募者は除外する。", responses=api_errors(401, 403, 404, 500))
async def list_applications(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
):
    request_item = await request_or_404(repository, current_user, request_id)
    if request_item["requesterId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    items = await application_repository.list_for_request(current_user, request_id)
    return {"items": [
        {**item, "helper": item.get("helper") or HELPERS[item["helperId"]]}
        for item in items
        if not is_blocked_pair(current_user.user_id, item["helperId"])
    ]}


@app.post("/requests/{request_id}/applications", response_model=ApplicationResponse, status_code=201, tags=["Applications"], summary="公開依頼へ応募", description="認証済み本人を支援者として応募する。自分の依頼、重複応募、公開中でない依頼には応募できない。", responses=api_errors(401, 403, 404, 409, 422, 500))
async def create_application(
    request_id: str,
    body: ApplicationInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
):
    request_item = await request_or_404(repository, current_user, request_id)
    if is_blocked_pair(current_user.user_id, request_item["requesterId"]):
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    return await create_application_service(
        application_repository, current_user,
        request_item, body.model_dump(),
    )


@app.post("/applications/{application_id}/withdraw", response_model=ApplicationResponse, tags=["Applications"], summary="応募を取り下げ", description="応募した本人だけがapplied状態をwithdrawnへ遷移できる。", responses=api_errors(401, 403, 404, 409, 500))
async def withdraw_application(
    application_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    repository: ApplicationRepository = Depends(application_repository_dependency),
):
    return await withdraw_application_service(repository, current_user, application_id)


@app.post("/applications/{application_id}/select", response_model=MatchResponse, status_code=201, tags=["Applications"], summary="応募者を選択してマッチ成立", description="依頼者本人だけが応募者を選択できる。expectedVersionで定員超過と同時更新を防ぎ、不一致・定員到達・選択不能状態は409。定員到達時は依頼をmatched、未選択応募をnot_selectedへ遷移する。", responses=api_errors(401, 403, 404, 409, 422, 500))
async def select_application(
    application_id: str,
    body: SelectionInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
):
    existing = await application_repository.get(current_user, application_id)
    blocked = existing is not None and is_blocked_pair(
        current_user.user_id, existing["helperId"]
    )
    application, request_item = await select_application_service(
        application_repository,
        repository,
        current_user,
        application_id,
        body.expectedVersion,
        blocked=blocked,
        helper_verified=(
            existing is not None
            and users_store.get(existing["helperId"], {}).get("verificationStatus")
            == "approved"
        ),
    )
    match = {
        "id": new_id("match"),
        "requestId": request_item["id"],
        "requesterId": request_item["requesterId"],
        "helperId": application["helperId"],
        "status": "matched",
        "requesterConfirmed": False,
        "helperConfirmed": False,
        "matchedAt": now_iso(),
        "completedAt": None,
        "version": 1,
    }
    matches[match["id"]] = match
    messages[match["id"]] = []
    return match


@app.get("/matches/{match_id}", response_model=MatchResponse, tags=["Matches"], summary="マッチ詳細を取得", description="依頼者と選択された支援者本人だけが取得できる。", responses=api_errors(401, 403, 404, 500))
async def get_match(match_id: str, current_user: CurrentUser = Depends(get_current_user)):
    match = match_or_404(match_id)
    ensure_match_participant(match, current_user.user_id)
    other_user_id = (
        match["helperId"]
        if match["requesterId"] == current_user.user_id
        else match["requesterId"]
    )
    if is_blocked_pair(current_user.user_id, other_user_id):
        raise HTTPException(404, detail={"code": "MATCH_NOT_FOUND"})
    return match


@app.get("/matches/{match_id}/messages", response_model=MessageListResponse, tags=["Messages"], summary="チャット履歴を取得", description="成立したマッチの当事者だけが取得できる。送信日時の昇順。ブロックした相手のメッセージは除外する。nextCursorは次ページなしでnull（現行実装は常にnull）。", responses=api_errors(401, 403, 404, 500))
async def list_messages(
    match_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    match = match_or_404(match_id)
    ensure_match_participant(match, current_user.user_id)
    return {
        "items": [
            item for item in messages.get(match_id, [])
            if not (
                item["senderId"] != current_user.user_id
                and is_blocked_pair(current_user.user_id, item["senderId"])
            )
        ],
        "nextCursor": None,
    }


@app.post("/matches/{match_id}/messages", response_model=MessageResponse, status_code=201, tags=["Messages"], summary="チャットメッセージを送信", description="マッチ当事者だけが送信できる。senderIdとsentAtはセッションとサーバー時刻から決定する。", responses=api_errors(401, 403, 404, 422, 500))
async def create_message(
    match_id: str,
    body: MessageInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    ensure_match_participant(match_or_404(match_id), current_user.user_id)

    # 個人情報の検知ロジック(現在は電話番号とメールアドレスのみ、必要に応じて"address"などを追加)
    moderation_status = "allowed"
    for pii_type, _, pattern in PII_MASK_RULES:
        if pii_type in {"phone", "email"} and pattern.search(body.body):
            moderation_status = "flagged"

            # --- 送信確認フロー（別パターン）有効化時にコメントアウトを外す ---
            # if getattr(body, "confirmed", False) is not True:
            #     raise HTTPException(422, detail={
            #         "code": "CONFIRMATION_REQUIRED",
            #         "message": "個人情報が含まれている可能性があります。送信するには確認が必要です"
            #     })
            # -----------------------------------------------------------------

            break

    item = {
        "id": new_id("msg"),
        "matchId": match_id,
        "senderId": current_user.user_id,
        "body": body.body,
        "sentAt": now_iso(),
        "readAt": None,
        "moderationStatus": moderation_status,
    }
    messages.setdefault(match_id, []).append(item)
    return item


# 完了確認を受け付けるマッチ状態。ここを明示しないと disputed や completed を
# 完了操作で上書きできる。状態を変える前に検査すること。
COMPLETABLE_MATCH_STATUSES = {"matched", "completion_pending"}


@app.post("/matches/{match_id}/complete", response_model=MatchResponse, tags=["Matches"], summary="活動完了を確認", description="依頼者と支援者本人だけが自分の役割で確認できる。片方のみはcompletion_pending、双方確認後はcompleted。disputedまたはcompletedへの操作は409。現行実装では同じ当事者の再確認は冪等に成功する。", responses=api_errors(401, 403, 404, 409, 422, 500))
async def complete_match(
    match_id: str,
    body: CompletionInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    match = match_or_404(match_id)
    actor_role = ensure_match_participant(match, current_user.user_id)
    if body.actorRole != actor_role:
        raise HTTPException(403, detail={"code": "ACTOR_ROLE_MISMATCH"})
    if match["status"] not in COMPLETABLE_MATCH_STATUSES:
        raise HTTPException(409, detail={"code": "MATCH_NOT_COMPLETABLE"})
    match[f"{actor_role}Confirmed"] = True
    if match["requesterConfirmed"] and match["helperConfirmed"]:
        match["status"] = "completed"
        match["completedAt"] = now_iso()
        new_request_status = "completed"
    else:
        match["status"] = "completion_pending"
        new_request_status = "completion_pending"
    await repository.set_status(
        current_user, match["requestId"], new_request_status, bump_version=False,
    )
    return match


@app.post("/matches/{match_id}/dispute", response_model=MatchResponse, tags=["Matches"], summary="マッチングキャンセルを申告", description="当事者が理由を付けてマッチと依頼をdisputedへ遷移する。completedまたは既にdisputedの場合は409。", responses=api_errors(401, 403, 404, 409, 422, 500))
async def dispute_match(
    match_id: str,
    body: DisputeInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    match = match_or_404(match_id)
    ensure_match_participant(match, current_user.user_id)
    if match["status"] in {"completed", "disputed"}:
        raise HTTPException(409, detail={"code": "MATCH_NOT_DISPUTABLE"})
    match.update({"status": "disputed", "disputeReason": body.reason, "disputedAt": now_iso()})
    await request_or_404(repository, current_user, match["requestId"])
    await repository.set_status(
        current_user, match["requestId"], "disputed", bump_version=False,
    )
    return match


@app.post("/matches/{match_id}/reviews", response_model=ReviewResponse, status_code=201, tags=["Reviews"], summary="完了した相手をレビュー", description="completedのマッチ当事者だけが相手へ1件投稿できる。未完了または重複投稿は409。", responses=api_errors(401, 403, 404, 409, 422, 500))
async def create_review(
    match_id: str,
    body: ReviewInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    match = match_or_404(match_id)
    actor_role = ensure_match_participant(match, current_user.user_id)
    if match["status"] != "completed":
        raise HTTPException(409, detail={"code": "MATCH_NOT_COMPLETED"})
    if any(
        review["matchId"] == match_id and review["reviewerId"] == current_user.user_id
        for review in reviews.values()
    ):
        raise HTTPException(409, detail={"code": "DUPLICATE_REVIEW"})
    item = {
        "id": new_id("review"),
        "matchId": match_id,
        "reviewerId": current_user.user_id,
        "revieweeId": match["helperId"] if actor_role == "requester" else match["requesterId"],
        **body.model_dump(),
        "createdAt": now_iso(),
    }
    reviews[item["id"]] = item
    return item


@app.post("/achievements/generate", response_model=AchievementResponse, status_code=201, tags=["Achievements"], summary="AI実績プロフィールを生成", description="completedのマッチ当事者だけが生成できる開発用AIモック。個人情報を含めず、公開には本人承認が必要。", responses=api_errors(401, 403, 404, 409, 422, 500))
async def generate_achievement(
    body: AchievementInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    match = match_or_404(body.matchId)
    ensure_match_participant(match, current_user.user_id)
    if match["status"] != "completed":
        raise HTTPException(409, detail={"code": "MATCH_NOT_COMPLETED"})
    request_item = await request_or_404(repository, current_user, match["requestId"])
    item = {
        "id": new_id("ach"),
        "userId": match["helperId"],
        "matchId": match["id"],
        "generatedText": "地域住民の依頼に対応し、安全に配慮しながら支援活動を完了した。",
        "facts": {"category": request_item["category"], "minutes": request_item["estimatedMinutes"]},
        "visibility": body.visibility,
        "status": "generated",
        "modelName": "mock-model",
        "promptVersion": "mock-v1",
        "generatedAt": now_iso(),
        "approvedAt": None,
    }
    achievements[item["id"]] = item
    return item


@app.patch("/achievements/visibility", response_model=AchievementResponse, tags=["Achievements"], summary="AI実績の公開範囲を更新", description="実績の対象本人だけが変更できる。public指定はapproved=trueによる本人承認が必須。", responses=api_errors(401, 403, 404, 409, 422, 500))
async def update_achievement_visibility(
    body: AchievementVisibilityInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    item = achievements.get(body.achievementId)
    if not item:
        raise HTTPException(404, detail={"code": "ACHIEVEMENT_NOT_FOUND"})
    if item["userId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if body.visibility == "public" and not body.approved:
        raise HTTPException(409, detail={"code": "ACHIEVEMENT_APPROVAL_REQUIRED"})
    item["visibility"] = body.visibility
    if body.approved:
        item["approvedAt"] = now_iso()
        item["status"] = "approved"
    return item


@app.get("/character-progress", response_model=CharacterProgressResponse, tags=["Character"], summary="自分のキャラクター進捗を取得", description="認証済み本人が支援者として完了したマッチだけを集計し、累計ポイント・支援回数・段階・次段階までのポイント・表示キャラクター識別子を返す。集計値はクライアント入力を使わない。", responses=api_errors(401, 500))
async def get_character_progress(
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    helps: list[character.CompletedHelp] = []
    for match in matches.values():
        if match["helperId"] != current_user.user_id or match["status"] != "completed":
            continue
        # 依頼が読めないとき（削除済みなど）は活動時間を0として回数だけ数える。
        request_item = await repository.get(current_user, match["requestId"])
        minutes = request_item["estimatedMinutes"] if request_item else 0
        helps.append({"matchId": match["id"], "estimatedMinutes": minutes})
    return character.build_progress(current_user.user_id, helps)


@app.post("/verifications", response_model=VerificationResponse, status_code=201, tags=["Verification"], summary="本人確認を申請", description="大学メールまたは学生証で申請する開発用モック。学生証方式は非公開ストレージキーが必須だが、キーや画像はレスポンスに含めない。審査中の重複申請は409。", responses=api_errors(401, 409, 422, 500))
async def create_verification(
    body: VerificationInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: UploadRepository = Depends(upload_repository_dependency),
):
    if body.method == "student_card" and not body.uploadId:
        raise HTTPException(422, detail={"code": "UPLOAD_REQUIRED"})
    # 重複確認を画像の確定より先に行い、二重申請でアップロードを消費させない。
    if any(
        item["status"] == "pending" and item["userId"] == current_user.user_id
        for item in verifications.values()
    ):
        raise HTTPException(409, detail={"code": "VERIFICATION_ALREADY_PENDING"})
    image = None
    if body.uploadId:
        await owned_stored_upload(
            repository, body.uploadId, current_user, "verification_document"
        )
        image = await repository.promote_to_image(body.uploadId, current_user.user_id)
        if image is None:
            raise HTTPException(409, detail={"code": "UPLOAD_CONTENT_MISSING"})
    item = {
        "id": new_id("verification"),
        "userId": current_user.user_id,
        "method": body.method,
        # 画像の参照はサーバー内部にだけ持つ。レスポンスにも監査ログにも出さない。
        "_imageId": image["id"] if image else None,
        "status": "pending",
        "createdAt": now_iso(),
    }
    verifications[item["id"]] = item
    users_store[current_user.user_id]["verificationStatus"] = "pending"
    return item


@app.post("/reports", response_model=ReportResponse, status_code=201, tags=["Safety"], summary="違反・危険行為を通報", description="通報者はセッションから決定する。詐欺または危険作業の依頼通報はhighとなり、対象依頼をsuspendedへ自動遷移する。", responses=api_errors(401, 422, 500))
async def create_report(
    body: ReportInput,
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
):
    item = {
        "id": new_id("report"),
        "reporterId": current_user.user_id,
        **body.model_dump(),
        "severity": "high" if body.reason in {"fraud", "dangerous_work"} else "medium",
        "status": "open",
        "createdAt": now_iso(),
    }
    reports[item["id"]] = item
    record_audit_event(
        actor_id=current_user.user_id,
        event_type="report_created",
        target_type=body.targetType,
        target_id=body.targetId,
        detail={"reportId": item["id"], "severity": item["severity"]},
    )
    if item["severity"] == "high" and body.targetType == "request":
        try:
            target_id = UUID(body.targetId)
        except ValueError:
            target_id = None
        if target_id is not None:
            await repository.set_status(current_user, str(target_id), "suspended")
            record_audit_event(
                actor_id=current_user.user_id,
                event_type="request_auto_suspended",
                target_type="request",
                target_id=body.targetId,
                detail={"reportId": item["id"]},
            )
    return item


@app.post("/users/{user_id}/block", response_model=BlockResponse, status_code=201, tags=["Safety"], summary="利用者をブロックまたは解除", description="blocked=trueでブロック、falseで解除する。セッション本人との関係として保存し、対象との依頼・応募・メッセージを非表示にする。自分自身は指定不可。", responses=api_errors(401, 404, 422, 500))
async def set_user_block(
    user_id: str,
    body: BlockInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    if user_id == current_user.user_id:
        raise HTTPException(422, detail={"code": "SELF_BLOCK_NOT_ALLOWED"})
    if user_id not in users_store:
        raise HTTPException(404, detail={"code": "USER_PROFILE_NOT_FOUND"})
    relation = (current_user.user_id, user_id)
    if body.blocked:
        blocks.add(relation)
    else:
        blocks.discard(relation)
    record_audit_event(
        actor_id=current_user.user_id,
        event_type="user_blocked" if body.blocked else "user_unblocked",
        target_type="user",
        target_id=user_id,
    )
    return {"userId": user_id, "blocked": relation in blocks, "updatedAt": now_iso()}
