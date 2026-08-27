from datetime import datetime, timezone
import logging
import math
import os
import re
from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.auth import (
    SUPERTOKENS_ENABLED, CurrentUser, configure_user_creator, configure_user_lookup,
    cors_headers,
)
from app.repositories.matches import (
    MatchRepository,
    MatchRepositoryError,
    configure_match_block_checker,
    configure_match_user_active_checker,
)
if SUPERTOKENS_ENABLED:
    from supertokens_python.framework.fastapi import get_middleware
from app.routers import system_router
from app.schemas import LocationResolveInput


app = FastAPI(
    title="たすけの輪 API",
    version="0.1.0",
    description=(
        "地域の依頼と支援者をつなぐAPI契約。業務APIはSuperTokensのHttpOnly Cookie"
        "セッションが必須で、ユーザーID・ロール・送信日時はサーバーが決定する。"
        "`/auth/*` はSuperTokensが提供する。依頼・応募・マッチ・チャット・完了・dispute"
        "はRepositoryに保存されるが、review・AI・本人確認は現在開発用インメモリ実装である。"
        "`/_mock/reset` は明示的に有効化"
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
    422: "VALIDATION_ERROR",
    500: "INTERNAL_SERVER_ERROR",
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
    global reviews, achievements
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


async def match_or_404(
    repository: MatchRepository, actor: CurrentUser, match_id: str
) -> dict[str, Any]:
    match = await repository.get(actor, match_id)
    if match is None:
        raise HTTPException(404, detail={"code": "MATCH_NOT_FOUND"})
    return match


def raise_match_repository_error(error: MatchRepositoryError) -> None:
    if error.code in {"APPLICATION_NOT_FOUND", "REQUEST_NOT_FOUND", "MATCH_NOT_FOUND"}:
        status_code = 404
    elif error.code in {"ROLE_FORBIDDEN", "ACTOR_ROLE_MISMATCH", "MESSAGE_FORBIDDEN"}:
        status_code = 403
    else:
        status_code = 409
    detail: dict[str, Any] = {"code": error.code}
    if error.current_version is not None:
        detail["currentVersion"] = error.current_version
    raise HTTPException(status_code, detail=detail) from error


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


configure_match_block_checker(is_blocked_pair)


def is_active_user(user_id: str) -> bool:
    user = users_store.get(user_id)
    return user is not None and user.get("status") == "active"


configure_match_user_active_checker(is_active_user)


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


from app.routers.community import router as community_router
from app.routers.development import router as development_router
from app.routers.matching import router as matching_router
from app.routers.profile import router as profile_router
from app.routers.requests import router as requests_router


app.include_router(development_router)
app.include_router(profile_router)
app.include_router(requests_router)
app.include_router(matching_router)
app.include_router(community_router)
