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
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.auth import (
    SUPERTOKENS_ENABLED, CurrentUser, configure_user_creator, configure_user_lookup,
    cors_headers, get_current_user,
)
from app.db import actor_connection, admin_connection
if SUPERTOKENS_ENABLED:
    from supertokens_python.framework.fastapi import get_middleware
from app.routers import system_router
from app.schemas import (
    AchievementInput, AchievementVisibilityInput, ApplicationInput,
    BlockInput, CompletionInput, DisputeInput, MessageInput, ProfileUpdateInput,
    ReportInput, RequestInput, RequestUpdateInput, ReviewInput, SelectionInput,
    StructureInput, VerificationInput,
)


app = FastAPI(
    title="たすけの輪 Mock API",
    version="0.1.0",
    description="フロントエンド開発専用。認証と外部サービスは模擬である。",
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
    (
        "email",
        "[メールアドレス]",
        re.compile(r"[A-Za-z0-9Ａ-Ｚａ-ｚ０-９._%+－-]+[@＠][A-Za-z0-9Ａ-Ｚａ-ｚ０-９.-]+[.．][A-Za-zＡ-Ｚａ-ｚ]{2,}"),
    ),
    (
        "phone",
        "[電話番号]",
        re.compile(r"(?<![0-9０-９])[0０][0-9０-９]{1,4}[-ー－―]?[0-9０-９]{1,4}[-ー－―]?[0-9０-９]{3,4}(?![0-9０-９])"),
    ),
    (
        "postal_code",
        "[郵便番号]",
        re.compile(r"〒?\s*[0-9０-９]{3}[-ー－―][0-9０-９]{4}"),
    ),
    (
        "certificate_number",
        "[証明書番号]",
        re.compile(r"(?:免許証|学生証|証明書)(?:番号|No[.．]?)?\s*[:：]?\s*[A-Za-zＡ-Ｚａ-ｚ0-9０-９-]{5,}"),
    ),
    (
        "address",
        "[詳細住所]",
        re.compile(r"(?:東京都|北海道|(?:京都|大阪)府|.{2,3}県).{1,20}(?:市|区|町|村).{1,30}(?:[0-9０-９]+(?:[-ー－―丁目番地号][0-9０-９]*)+|丁目)"),
    ),
    (
        "name",
        "[氏名]",
        re.compile(r"(?:氏名|名前)\s*(?:は|[:：])?\s*[一-龥々]{2,8}(?:\s|　)?[一-龥々]{1,8}"),
    ),
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
    masked_text: str, _area_code: str
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


StructureLLMClient = Callable[[str, str], Awaitable[dict[str, Any]]]
structure_llm_client: StructureLLMClient = default_structure_llm_client


def configure_structure_llm_client(client: StructureLLMClient) -> None:
    global structure_llm_client
    structure_llm_client = client

RECOMMENDATION_WEIGHTS = {
    "preferredCategory": 30,
    "skillMatch": 25,
    "distance": 20,
    "availability": 15,
    "pastAchievement": 10,
}


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


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def get_or_404(store: dict, entity_id: str, error_code: str) -> dict:
    item = store.get(entity_id)
    if item is None:
        raise HTTPException(404, detail={"code": error_code})
    return item


def encode_recommendation_cursor(score: float, request_id: str) -> str:
    payload = json.dumps([score, request_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_recommendation_cursor(cursor: str) -> tuple[float, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        score, request_id = json.loads(base64.urlsafe_b64decode(padded).decode())
        return float(score), str(request_id)
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
        raise HTTPException(422, detail={"code": "INVALID_CURSOR"}) from exc


def is_expired(request_item: dict[str, Any]) -> bool:
    expires_at = request_item.get("expiresAt")
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.now(
            timezone.utc
        )
    except (ValueError, TypeError):
        return True


def users_are_blocked(user_id: str, other_user_id: str) -> bool:
    return (
        other_user_id in blocks
        or (user_id, other_user_id) in blocks
        or (other_user_id, user_id) in blocks
    )


def recommendation_score(
    request_item: dict[str, Any], profile: dict[str, Any]
) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []
    preferred_categories = set(profile.get("preferredCategories", []))
    cold_start = not (
        preferred_categories
        or profile.get("skillTags")
        or profile.get("availableTimes")
        or profile.get("categoryAchievements")
    )
    if cold_start and request_item.get("areaCode") == profile.get("areaCode"):
        score += 10
        reasons.append("登録地域に近い新着依頼")
    if request_item["category"] in preferred_categories:
        score += RECOMMENDATION_WEIGHTS["preferredCategory"]
        reasons.append("希望カテゴリと一致")

    required_skills = set(request_item.get("requiredSkills", []))
    user_skills = set(profile.get("skillTags", []))
    matched_skills = sorted(required_skills & user_skills)
    if required_skills and matched_skills:
        score += RECOMMENDATION_WEIGHTS["skillMatch"] * (
            len(matched_skills) / len(required_skills)
        )
        reasons.append(f"スキル一致: {', '.join(matched_skills)}")

    distance_km = float(request_item.get("distanceKm", 999))
    max_distance_km = float(profile.get("maxDistanceKm", 10))
    if distance_km <= max_distance_km:
        distance_score = (
            RECOMMENDATION_WEIGHTS["distance"]
            if max_distance_km == 0 and distance_km == 0
            else RECOMMENDATION_WEIGHTS["distance"]
            * max(0.0, 1 - distance_km / max_distance_km)
            if max_distance_km > 0
            else 0
        )
        score += distance_score
        reasons.append(f"活動範囲内（約{distance_km:g}km）")

    available_times = profile.get("availableTimes", [])
    if request_item["scheduledAt"] in available_times:
        score += RECOMMENDATION_WEIGHTS["availability"]
        reasons.append("対応可能日時と一致")

    category_achievements = profile.get("categoryAchievements", {})
    achievement_count = int(category_achievements.get(request_item["category"], 0))
    if achievement_count:
        score += RECOMMENDATION_WEIGHTS["pastAchievement"] * min(
            achievement_count / 5, 1
        )
        reasons.append(f"同カテゴリの完了実績{achievement_count}件")

    if not reasons:
        reasons.append("募集中の新着依頼")
    return round(score, 2), reasons


INITIAL_REQUESTS = [
    {
        "id": "req_1024",
        "requesterId": "usr_101",
        "title": "犬の散歩をお願いしたい",
        "description": "体調不良のため、小型犬の散歩を30分お願いしたいです。",
        "category": "pet_support",
        "riskLevel": "medium",
        "areaCode": "AREA-001",
        "areaLabel": "大学周辺・約1km",
        "distanceKm": 1.2,
        "scheduledAt": "2026-08-19T17:00:00+09:00",
        "estimatedMinutes": 30,
        "requiredHelpers": 1,
        "acceptedHelpers": 0,
        "status": "published",
        "version": 3,
        "warnings": ["犬の性格とリードの状態を事前に確認してください"],
        "createdAt": "2026-08-18T10:00:00+09:00",
    },
    {
        "id": "req_1025",
        "requesterId": "usr_301",
        "title": "玄関前の雪かきを手伝ってほしい",
        "description": "玄関から歩道までの雪かきをお願いします。",
        "category": "snow_removal",
        "riskLevel": "medium",
        "areaCode": "AREA-001",
        "areaLabel": "大学北側・約2km",
        "distanceKm": 2.1,
        "scheduledAt": "2026-08-20T09:00:00+09:00",
        "estimatedMinutes": 45,
        "requiredHelpers": 2,
        "acceptedHelpers": 0,
        "status": "published",
        "version": 1,
        "warnings": ["悪天候時は活動を中止してください"],
        "createdAt": "2026-08-18T11:00:00+09:00",
    },
]

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
            "role": "requester",
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


@app.post("/_mock/reset", tags=["Mock control"])
async def reset_mock(
    _: None = Depends(require_mock_environment),
    current_user: CurrentUser = Depends(get_current_user),
):
    reset_store()
    async with admin_connection() as conn:
        await conn.execute("select app.mock_reset_requests()")
    return {"reset": True}


@app.get("/profile", tags=["Profile"])
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    return users_store[current_user.user_id]


@app.patch("/profile", tags=["Profile"])
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


@app.post("/requests/structure", tags=["Requests"])
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
    if any(word in body.text for word in ["電気工事", "医療行為", "介護", "送迎"]):
        raise HTTPException(422, detail={"code": "PROHIBITED_REQUEST", "riskLevel": "prohibited"})
    try:
        result = await structure_llm_client(masking["maskedText"], body.areaCode)
    except Exception:
        logger.warning("Request structure service failed after masking")
        raise HTTPException(503, detail={"code": "STRUCTURE_SERVICE_UNAVAILABLE"})
    masking_metrics["submitted"] += 1
    return {
        **result,
        "masking": {
            "detections": masking["detections"],
            "ruleVersion": masking["ruleVersion"],
            "confirmed": body.maskingConfirmed,
        },
        "requiresConfirmation": True,
    }


@app.post("/requests/masking-preview", tags=["Requests"])
async def preview_request_masking(
    body: StructureInput,
    _current_user: CurrentUser = Depends(get_current_user),
):
    masking_metrics["previewed"] += 1
    return mask_request_text(body.text)


@app.get("/requests", tags=["Requests"])
async def list_requests(
    category: str | None = None,
    areaCode: str | None = None,
    scheduledFrom: datetime | None = None,
    scheduledTo: datetime | None = None,
    maxDistanceKm: float | None = Query(default=None, gt=0, le=100),
    requiredHelpers: int | None = Query(default=None, ge=1, le=5),
    verificationStatus: str | None = Query(
        default=None, pattern="^(unverified|pending|approved|rejected)$",
    ),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    async with actor_connection(current_user) as conn:
        rows = await conn.fetch(
            """
            select r.id, r.title, r.original_text, r.category_id, r.risk_level,
                   r.area_code, r.scheduled_at, r.estimated_minutes, r.required_helpers,
                   r.status, r.version, r.created_at, r.updated_at,
                   app.auth_subject_of(r.requester_id) as requester_auth_subject,
                   (select count(*) from matches m where m.request_id = r.id) as accepted_helpers
              from requests r
             where r.status = 'published'
               and ($1::text is null or r.category_id = $1)
               and ($2::text is null or r.area_code = $2)
             order by r.created_at desc, r.id desc
             limit $3
            """,
            category,
            areaCode,
            limit,
        )
    items = [_request_row_to_api(row) for row in rows]
    items = [
        item for item in items
        if not is_blocked_pair(current_user.user_id, item["requesterId"])
    ]
    return {"items": items, "nextCursor": None}


@app.get("/requests/recommendations", tags=["Requests"])
async def list_request_recommendations(
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
):
    profile = users_store[current_user.user_id]
    ranked_items = []
    for request_item in requests_store.values():
        if request_item["requesterId"] == current_user.user_id:
            continue
        if request_item["status"] != "published" or is_expired(request_item):
            continue
        if request_item["acceptedHelpers"] >= request_item["requiredHelpers"]:
            continue
        if users_are_blocked(current_user.user_id, request_item["requesterId"]):
            continue
        if (
            request_item.get("verificationRequired")
            and profile.get("verificationStatus") != "approved"
        ):
            continue
        if any(
            application["requestId"] == request_item["id"]
            and application["helperId"] == current_user.user_id
            and application["status"] not in {"withdrawn", "cancelled", "not_selected"}
            for application in applications.values()
        ):
            continue

        score, reasons = recommendation_score(request_item, profile)
        ranked_items.append(
            {
                "id": request_item["id"],
                "title": request_item["title"],
                "category": request_item["category"],
                "areaCode": request_item["areaCode"],
                "areaLabel": request_item["areaLabel"],
                "distanceKm": request_item["distanceKm"],
                "scheduledAt": request_item["scheduledAt"],
                "estimatedMinutes": request_item["estimatedMinutes"],
                "requiredHelpers": request_item["requiredHelpers"],
                "requiredSkills": request_item.get("requiredSkills", []),
                "verificationRequired": request_item.get("verificationRequired", False),
                "recommendationScore": score,
                "recommendationReasons": reasons,
            }
        )

    ranked_items.sort(key=lambda item: (-item["recommendationScore"], item["id"]))
    start = 0
    if cursor:
        cursor_key = decode_recommendation_cursor(cursor)
        for index, item in enumerate(ranked_items):
            if (item["recommendationScore"], item["id"]) == cursor_key:
                start = index + 1
                break
        else:
            raise HTTPException(422, detail={"code": "INVALID_CURSOR"})
    page = ranked_items[start : start + limit]
    next_cursor = None
    if start + limit < len(ranked_items) and page:
        last_item = page[-1]
        next_cursor = encode_recommendation_cursor(
            last_item["recommendationScore"], last_item["id"]
        )
    return {
        "items": page,
        "nextCursor": next_cursor,
        "scoringWeights": RECOMMENDATION_WEIGHTS,
        "applicationPolicy": "応募時に認可と最新の募集状態を再検証します",
    }


@app.post("/requests", status_code=201, tags=["Requests"])
async def create_request(
    body: RequestInput,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(get_current_user),
):
    cache_key = ("create_request", current_user.user_id, idempotency_key)
    if cache_key in idempotency_store:
        return idempotency_store[cache_key]
    async with actor_connection(current_user) as conn:
        row = await conn.fetchrow(
            """
            insert into requests (
                requester_id, title, original_text, category_id, risk_level,
                area_code, scheduled_at, estimated_minutes, required_helpers
            ) values ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            returning id, title, original_text, category_id, risk_level,
                      area_code, scheduled_at, estimated_minutes, required_helpers,
                      status, version, created_at, updated_at
            """,
            await conn.fetchval("select app.current_actor()"),
            body.title,
            body.description,
            body.category,
            body.riskLevel,
            body.areaCode,
            datetime.fromisoformat(body.scheduledAt),
            body.estimatedMinutes,
            body.requiredHelpers,
        )
        item = _request_row_to_api({**dict(row), "requester_auth_subject": current_user.user_id,
                                     "accepted_helpers": 0})
    idempotency_store[cache_key] = item
    return item


# #20: このエンドポイントは元々認証を要求せず、依頼の状態も検査していなかった。
# RLS は未認証アクター（app.actor_id 未設定）に一律 deny を返すため、Postgres へ
# 接続した時点で認証必須が構造として強制される。get_current_user() が無効な
# セッションを 401 で弾き、RLS が届かない行を 404 として隠す。
@app.get("/requests/{request_id}", tags=["Requests"])
async def get_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    async with actor_connection(current_user) as conn:
        item = await request_or_404(conn, request_id)
    if is_blocked_pair(current_user.user_id, item["requesterId"]):
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    return item


@app.patch("/requests/{request_id}", tags=["Requests"])
async def update_request(
    request_id: str,
    body: RequestUpdateInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    async with actor_connection(current_user) as conn:
        item = await request_or_404(conn, request_id)
        if item["requesterId"] != current_user.user_id:
            raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
        if item["status"] not in {"draft", "pending_review", "published"}:
            raise HTTPException(409, detail={"code": "REQUEST_NOT_EDITABLE"})
        if item["version"] != body.expectedVersion:
            raise HTTPException(
                409, detail={"code": "REQUEST_STATE_CONFLICT", "currentVersion": item["version"]}
            )
        changes = body.model_dump(exclude={"expectedVersion"}, exclude_none=True)
        if "requiredHelpers" in changes and changes["requiredHelpers"] < item["acceptedHelpers"]:
            raise HTTPException(409, detail={"code": "HELPER_COUNT_CONFLICT"})
        if not changes:
            return item
        # version は関数側の WHERE でも検査する。request_or_404 の読み取りと
        # この呼び出しの間に他の更新が割り込んでいたら、0件更新で楽観ロックが働く。
        updated = await conn.fetchval(
            "select app.update_request($1, $2, $3, $4, $5, $6, $7)",
            uuid.UUID(request_id),
            item["version"],
            changes.get("title"),
            changes.get("description"),
            datetime.fromisoformat(changes["scheduledAt"]) if "scheduledAt" in changes else None,
            changes.get("estimatedMinutes"),
            changes.get("requiredHelpers"),
        )
        if updated is None:
            raise HTTPException(
                409, detail={"code": "REQUEST_STATE_CONFLICT", "currentVersion": item["version"]}
            )
        return await request_or_404(conn, request_id)


@app.delete("/requests/{request_id}", status_code=204, tags=["Requests"])
async def cancel_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    async with actor_connection(current_user) as conn:
        item = await request_or_404(conn, request_id)
        if item["requesterId"] != current_user.user_id:
            raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
        if item["status"] in {"completed", "cancelled"}:
            raise HTTPException(409, detail={"code": "INVALID_REQUEST_TRANSITION"})
        await conn.fetchval(
            "select app.set_request_status($1, 'cancelled')", uuid.UUID(request_id)
        )
    for application in applications.values():
        if application["requestId"] == request_id and application["status"] == "applied":
            application["status"] = "cancelled"
    return None


@app.get("/requests/{request_id}/applications", tags=["Applications"])
async def list_applications(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    async with actor_connection(current_user) as conn:
        request_item = await request_or_404(conn, request_id)
    if request_item["requesterId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    return {
        "items": [
            {**item, "helper": HELPERS[item["helperId"]]}
            for item in applications.values()
            if item["requestId"] == request_id
            and not is_blocked_pair(current_user.user_id, item["helperId"])
        ]
    }


@app.post("/requests/{request_id}/applications", status_code=201, tags=["Applications"])
async def create_application(
    request_id: str,
    body: ApplicationInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    request_item = request_or_404(request_id)
    if current_user.status != "active":
        raise HTTPException(403, detail={"code": "USER_SUSPENDED"})
    if current_user.role != "helper":
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if request_item["status"] != "published":
        raise HTTPException(409, detail={"code": "REQUEST_NOT_OPEN"})
    if parse_datetime(request_item["scheduledAt"]) <= datetime.now(timezone.utc):
        raise HTTPException(409, detail={"code": "REQUEST_EXPIRED"})
    if request_item["requesterId"] == current_user.user_id:
        raise HTTPException(403, detail={"code": "SELF_APPLICATION_NOT_ALLOWED"})
    if (
        request_item.get("verificationRequired", False)
        and current_user.verification_status != "approved"
    ):
        raise HTTPException(403, detail={"code": "VERIFICATION_REQUIRED"})
    if any(
        item["requestId"] == request_id
        and item["helperId"] == current_user.user_id
        and item["status"] not in {"withdrawn", "cancelled"}
        for item in applications.values()
    ):
        raise HTTPException(409, detail={"code": "DUPLICATE_APPLICATION"})
    item = {
        "id": new_id("app"),
        "requestId": request_id,
        "helperId": current_user.user_id,
        **body.model_dump(),
        "status": "applied",
        "createdAt": now_iso(),
    }
    applications[item["id"]] = item
    return item


@app.post("/applications/{application_id}/withdraw", tags=["Applications"])
async def withdraw_application(
    application_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.status != "active":
        raise HTTPException(403, detail={"code": "USER_SUSPENDED"})
    application = applications.get(application_id)
    if not application:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    if application["helperId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if application["status"] != "applied":
        raise HTTPException(409, detail={"code": "APPLICATION_NOT_WITHDRAWABLE"})
    application["status"] = "withdrawn"
    application["updatedAt"] = now_iso()
    return application


@app.post("/applications/{application_id}/select", status_code=201, tags=["Applications"])
async def select_application(
    application_id: str,
    body: SelectionInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    application = applications.get(application_id)
    if not application:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    if application["requestId"] != body.requestId:
        raise HTTPException(409, detail={"code": "APPLICATION_REQUEST_MISMATCH"})
    async with actor_connection(current_user) as conn:
        request_item = await request_or_404(conn, body.requestId)
        if request_item["requesterId"] != current_user.user_id:
            raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
        if request_item["version"] != body.expectedVersion:
            raise HTTPException(
                409,
                detail={
                    "code": "REQUEST_STATE_CONFLICT",
                    "currentVersion": request_item["version"],
                },
            )
        if application["status"] != "applied":
            raise HTTPException(409, detail={"code": "APPLICATION_NOT_SELECTABLE"})
        if request_item["acceptedHelpers"] >= request_item["requiredHelpers"]:
            raise HTTPException(409, detail={"code": "CAPACITY_REACHED"})
        # matches への insert が accepted_helpers の増分そのものなので、この値自体は
        # どこにも永続化しない。#7 が実装する排他ロック（トランザクション境界・
        # 同時実行制御）はここでは行わない。既存の振る舞いを壊さないための
        # 最小限の書き込みに留める。
        capacity_reached = (
            request_item["acceptedHelpers"] + 1 >= request_item["requiredHelpers"]
        )
        new_status = "matched" if capacity_reached else "matching"
        updated = await conn.fetchval(
            "select app.set_request_status($1, $2::request_status, $3)",
            uuid.UUID(request_item["id"]),
            new_status,
            request_item["version"],
        )
        if updated is None:
            raise HTTPException(
                409,
                detail={
                    "code": "REQUEST_STATE_CONFLICT",
                    "currentVersion": request_item["version"],
                },
            )
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


@app.get("/matches/{match_id}", tags=["Matches"])
async def get_match(match_id: str, current_user: CurrentUser = Depends(get_current_user)):
    match = match_or_404(match_id)
    ensure_match_participant(match, current_user.user_id)
    return match


@app.get("/matches/{match_id}/messages", tags=["Messages"])
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


@app.post("/matches/{match_id}/messages", status_code=201, tags=["Messages"])
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


@app.post("/matches/{match_id}/complete", tags=["Matches"])
async def complete_match(
    match_id: str,
    body: CompletionInput,
    current_user: CurrentUser = Depends(get_current_user),
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
    async with actor_connection(current_user) as conn:
        # The match participant check above is the authorization boundary.
        # A helper cannot directly read the request after it leaves the
        # published state under RLS, but must still be able to confirm
        # completion. The server-owned match supplies the request ID to the
        # constrained transition function.
        await conn.fetchval(
            "select app.set_request_status($1, $2::request_status, null, false)",
            uuid.UUID(match["requestId"]),
            new_request_status,
        )
    return match


@app.post("/matches/{match_id}/dispute", tags=["Matches"])
async def dispute_match(
    match_id: str,
    body: DisputeInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    match = match_or_404(match_id)
    ensure_match_participant(match, current_user.user_id)
    if match["status"] in {"completed", "disputed"}:
        raise HTTPException(409, detail={"code": "MATCH_NOT_DISPUTABLE"})
    match.update({"status": "disputed", "disputeReason": body.reason, "disputedAt": now_iso()})
    async with actor_connection(current_user) as conn:
        await request_or_404(conn, match["requestId"])
        await conn.fetchval(
            "select app.set_request_status($1, 'disputed', null, false)",
            uuid.UUID(match["requestId"]),
        )
    return match


@app.post("/matches/{match_id}/reviews", status_code=201, tags=["Reviews"])
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


@app.post("/achievements/generate", status_code=201, tags=["Achievements"])
async def generate_achievement(
    body: AchievementInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    match = match_or_404(body.matchId)
    ensure_match_participant(match, current_user.user_id)
    if match["status"] != "completed":
        raise HTTPException(409, detail={"code": "MATCH_NOT_COMPLETED"})
    async with actor_connection(current_user) as conn:
        request_item = await request_or_404(conn, match["requestId"])
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


@app.patch("/achievements/visibility", tags=["Achievements"])
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


@app.post("/verifications", status_code=201, tags=["Verification"])
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


@app.post("/reports", status_code=201, tags=["Safety"])
async def create_report(
    body: ReportInput,
    current_user: CurrentUser = Depends(get_current_user),
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
            target_id = uuid.UUID(body.targetId)
        except ValueError:
            target_id = None
        if target_id is not None:
            async with actor_connection(current_user) as conn:
                await conn.fetchval(
                    "select app.set_request_status($1, 'suspended')", target_id
                )
            record_audit_event(
                actor_id=current_user.user_id,
                event_type="request_auto_suspended",
                target_type="request",
                target_id=body.targetId,
                detail={"reportId": item["id"]},
            )
    return item


@app.post("/users/{user_id}/block", status_code=201, tags=["Safety"])
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
