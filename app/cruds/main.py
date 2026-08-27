from copy import deepcopy
import base64
import binascii
from datetime import datetime, timezone
import json
import logging
import math
import os
import re
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.auth import (
    SUPERTOKENS_ENABLED, CurrentUser, configure_user_creator, configure_user_lookup,
    cors_headers, get_current_user,
)
from app.repositories.requests import RequestRepository, get_request_repository
from app.repositories.applications import (
    ApplicationRepository, get_application_repository,
)
from app.services.applications import (
    create_application as create_application_service,
    withdraw_application as withdraw_application_service,
)
from app.services.requests import cancel_owned_request, require_request, update_owned_request
if SUPERTOKENS_ENABLED:
    from supertokens_python.framework.fastapi import get_middleware
from app.routers import system_router
from app.schemas import (
    AchievementInput, AchievementResponse, AchievementVisibilityInput,
    ApplicationInput, ApplicationListResponse, ApplicationResponse,
    BlockInput, BlockResponse, CompletionInput, DisputeInput, ErrorResponse,
    LocationResolveInput, LocationResolveResponse, MatchResponse, MessageInput,
    MaskingConfirmationResponse, MessageListResponse, MessageResponse,
    ProfileResponse, ProfileUpdateInput,
    ReportInput, ReportResponse, RequestInput, RequestListResponse, RequestResponse,
    RequestUpdateInput, ResetResponse, ReviewInput, ReviewResponse, SelectionInput,
    StructureInput, StructuredRequestResponse, VerificationInput, VerificationResponse,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("WEBSITE_DOMAIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=cors_headers(),
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
        422: ("VALIDATION_ERROR", "入力内容を確認してください"),
        500: ("INTERNAL_SERVER_ERROR", "サーバー内部でエラーが発生しました"),
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
    is_dog = "犬" in masked_text or "散歩" in masked_text
    return {
        "title": "犬の散歩をお願いしたい" if is_dog else "地域の手助けをお願いしたい",
        "description": masked_text,
        "category": "pet_support" if is_dog else "other",
        "scheduledAt": "2026-08-19T17:00:00+09:00",
        "estimatedMinutes": 30,
        "requiredHelpers": 1,
        "riskLevel": "medium" if is_dog else "low",
        "missingFields": ["犬の大きさ"] if is_dog and "小型" not in masked_text else [],
        "warnings": ["犬の性格とリードの状態を確認してください"] if is_dog else [],
    }


StructureLLMClient = Callable[[str, str | None], Awaitable[dict[str, Any]]]
structure_llm_client: StructureLLMClient = default_structure_llm_client


def configure_structure_llm_client(client: StructureLLMClient) -> None:
    global structure_llm_client
    structure_llm_client = client

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


async def request_repository_dependency() -> RequestRepository:
    """Resolve the configured repository without a test-time threadpool hop."""
    return get_request_repository()


async def application_repository_dependency() -> ApplicationRepository:
    """Resolve the application repository without a test-time threadpool hop."""
    return get_application_repository()


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
            "id": "usr_301", "displayName": "鈴木 雪", "role": "requester",
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


async def require_mock_environment() -> None:
    if not MOCK_RESET_ENABLED:
        raise HTTPException(404, detail={"code": "NOT_FOUND"})


@app.post("/_mock/reset", response_model=ResetResponse, tags=["Development mock"], summary="開発用モックデータを初期化", description="非本番かつMOCK_RESET_ENABLED=trueの場合だけ、認証済み利用者が実行できる。全モックデータを初期状態へ戻す。", responses=api_errors(401, 404, 500))
async def reset_mock(
    _: None = Depends(require_mock_environment),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
    application_repository: ApplicationRepository = Depends(
        application_repository_dependency
    ),
):
    reset_store()
    await repository.reset()
    await application_repository.reset()
    return {"reset": True}


@app.get("/profile", response_model=ProfileResponse, tags=["Profile"], summary="自分のプロフィールを取得", description="Cookieセッションの本人の公開可能なプロフィールだけを返す。", responses=api_errors(401, 403, 500))
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    return users_store[current_user.user_id]


@app.patch("/profile", response_model=ProfileResponse, tags=["Profile"], summary="自分のプロフィールを更新", description="表示名または概算地域を更新する。ユーザーID、ロール、本人確認状態は入力できない。", responses=api_errors(401, 403, 422, 500))
async def update_profile(
    body: ProfileUpdateInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, detail={"code": "NO_CHANGES"})
    profile = users_store[current_user.user_id]
    profile.update(changes)
    profile["updatedAt"] = now_iso()
    return profile


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


@app.post("/requests/structure", response_model=StructuredRequestResponse | MaskingConfirmationResponse, tags=["Requests"], summary="依頼文を構造化", description="自由記述を依頼候補へ構造化する開発用AIモック。個人情報をマスクし、検出時は確認を求める。結果は自動公開されない。", responses=api_errors(401, 422, 500))
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
    if any(word in masking["maskedText"] for word in ["電気工事", "医療行為", "介護", "送迎"]):
        raise HTTPException(422, detail={"code": "PROHIBITED_REQUEST", "riskLevel": "prohibited"})
    try:
        result = await structure_llm_client(masking["maskedText"], body.areaCode)
    except Exception:
        logger.warning("Request structure service failed after masking")
        raise HTTPException(503, detail={"code": "STRUCTURE_SERVICE_UNAVAILABLE"})
    masking_metrics["submitted"] += 1
    return {
        **result,
        "requiresConfirmation": True,
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


@app.get("/requests", response_model=RequestListResponse, tags=["Requests"], summary="公開依頼を検索", description="カテゴリ・概算地域で絞り込み、現在地または登録地域に近い順で返す。limit既定20、最大100。Repository内ではcreatedAt降順・ID降順。公開中のみを対象とし、ブロック関係の依頼は除外する。nextCursorは次ページがない場合nullで、現行実装は常にnull。", responses=api_errors(401, 422, 500))
async def list_requests(
    category: str | None = None,
    areaCode: str | None = None,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    consentGranted: bool = False,
    locationFailure: str | None = Query(
        default=None, pattern="^(denied|timeout|unsupported|unavailable)$"
    ),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    repository: RequestRepository = Depends(request_repository_dependency),
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
    items = await repository.list(
        current_user, category=category, area_code=areaCode, limit=limit,
    )
    items = [
        item for item in items
        if not is_blocked_pair(current_user.user_id, item["requesterId"])
    ]
    if latitude is not None and longitude is not None:
        items.sort(
            key=lambda item: distance_km(
                latitude, longitude, REGIONS.get(item["areaCode"], REGIONS["AREA-001"])
            )
        )
    else:
        items.sort(key=lambda item: item["areaCode"] != origin_area_code)
    return {
        "items": items,
        "nextCursor": None,
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
    item = await repository.create(current_user, {
        "title": body.title, "description": body.description, "category": body.category,
        "riskLevel": body.riskLevel, "areaCode": area_code,
        "scheduledAt": body.scheduledAt, "estimatedMinutes": body.estimatedMinutes,
        "requiredHelpers": body.requiredHelpers,
    })
    idempotency_store[cache_key] = item
    return item


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
    return await update_owned_request(
        repository, current_user, request_id, body.expectedVersion, changes,
    )


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
):
    application = applications.get(application_id)
    if not application:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    if application["requestId"] != body.requestId:
        raise HTTPException(409, detail={"code": "APPLICATION_REQUEST_MISMATCH"})
    request_item = await request_or_404(repository, current_user, body.requestId)
    if request_item["requesterId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if request_item["version"] != body.expectedVersion:
        raise HTTPException(409, detail={
            "code": "REQUEST_STATE_CONFLICT", "currentVersion": request_item["version"],
        })
    if application["status"] != "applied":
        raise HTTPException(409, detail={"code": "APPLICATION_NOT_SELECTABLE"})
    if request_item["acceptedHelpers"] >= request_item["requiredHelpers"]:
        raise HTTPException(409, detail={"code": "CAPACITY_REACHED"})
    capacity_reached = request_item["acceptedHelpers"] + 1 >= request_item["requiredHelpers"]
    new_status = "matched" if capacity_reached else "matching"
    updated = await repository.set_status(
        current_user, request_item["id"], new_status,
        expected_version=request_item["version"],
    )
    if not updated:
        raise HTTPException(409, detail={
            "code": "REQUEST_STATE_CONFLICT", "currentVersion": request_item["version"],
        })
    application["status"] = "selected"
    if capacity_reached:
        for other in applications.values():
            if other["requestId"] == request_item["id"] and other["status"] == "applied":
                other["status"] = "not_selected"
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
    }
    matches[match["id"]] = match
    messages[match["id"]] = []
    return match


@app.get("/matches/{match_id}", response_model=MatchResponse, tags=["Matches"], summary="マッチ詳細を取得", description="依頼者と選択された支援者本人だけが取得できる。", responses=api_errors(401, 403, 404, 500))
async def get_match(match_id: str, current_user: CurrentUser = Depends(get_current_user)):
    match = match_or_404(match_id)
    ensure_match_participant(match, current_user.user_id)
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
    item = {
        "id": new_id("msg"),
        "matchId": match_id,
        "senderId": current_user.user_id,
        "body": body.body,
        "sentAt": now_iso(),
        "readAt": None,
        "moderationStatus": "allowed",
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


@app.post("/verifications", response_model=VerificationResponse, status_code=201, tags=["Verification"], summary="本人確認を申請", description="大学メールまたは学生証で申請する開発用モック。学生証方式は非公開ストレージキーが必須だが、キーや画像はレスポンスに含めない。審査中の重複申請は409。", responses=api_errors(401, 409, 422, 500))
async def create_verification(
    body: VerificationInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    if body.method == "student_card" and not body.storageObjectKey:
        raise HTTPException(422, detail={"code": "STORAGE_OBJECT_REQUIRED"})
    if any(
        item["status"] == "pending" and item["userId"] == current_user.user_id
        for item in verifications.values()
    ):
        raise HTTPException(409, detail={"code": "VERIFICATION_ALREADY_PENDING"})
    item = {
        "id": new_id("verification"),
        "userId": current_user.user_id,
        **body.model_dump(),
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
