from copy import deepcopy
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import random
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
if SUPERTOKENS_ENABLED:
    from supertokens_python.framework.fastapi import get_middleware
from app.routers import system_router
from app.schemas import (
    AchievementInput, AchievementVisibilityInput, ApplicationInput,
    BlockInput, CompletionInput, DisputeInput, MessageInput, ProfileUpdateInput,
    ReportInput, RequestInput, RequestUpdateInput, ReviewInput, SelectionInput,
    StructureInput, StructuredRequestOutput, VerificationInput,
)
from pydantic import ValidationError


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

MAX_LLM_RETRIES = 2
RETRYABLE_LLM_FAILURES = {"timeout", "connection", "rate_limit", "server", "invalid_response"}
llm_failure_metrics = {
    "timeout": 0,
    "connection": 0,
    "rate_limit": 0,
    "server": 0,
    "invalid_response": 0,
    "authentication": 0,
    "client": 0,
    "fallback": 0,
}


class LLMServiceError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"LLM service returned status {status_code}")
        self.status_code = status_code


async def default_structure_generator(body: StructureInput) -> dict[str, Any]:
    is_dog = "犬" in body.text or "散歩" in body.text
    return {
        "title": "犬の散歩をお願いしたい" if is_dog else "地域の手助けをお願いしたい",
        "description": body.text,
        "category": "pet_support" if is_dog else "other",
        "scheduledAt": "2026-08-19T17:00:00+09:00",
        "estimatedMinutes": 30,
        "requiredHelpers": 1,
        "riskLevel": "medium" if is_dog else "low",
        "missingFields": ["犬の大きさ"] if is_dog and "小型" not in body.text else [],
        "warnings": ["犬の性格とリードの状態を確認してください"] if is_dog else [],
    }


StructureGenerator = Callable[[StructureInput], Awaitable[dict[str, Any] | str]]
RetrySleeper = Callable[[float], Awaitable[None]]
structure_generator: StructureGenerator = default_structure_generator
retry_sleeper: RetrySleeper = asyncio.sleep


def configure_structure_generator(generator: StructureGenerator) -> None:
    global structure_generator
    structure_generator = generator


def configure_retry_sleeper(sleeper: RetrySleeper) -> None:
    global retry_sleeper
    retry_sleeper = sleeper


def classify_llm_failure(exc: Exception) -> tuple[str, bool]:
    if isinstance(exc, TimeoutError):
        return "timeout", True
    if isinstance(exc, ConnectionError):
        return "connection", True
    if isinstance(exc, (json.JSONDecodeError, ValidationError, KeyError, TypeError)):
        return "invalid_response", True
    if isinstance(exc, LLMServiceError):
        if exc.status_code == 429:
            return "rate_limit", True
        if 500 <= exc.status_code <= 599:
            return "server", True
        if exc.status_code in {401, 403}:
            return "authentication", False
        return "client", False
    return "server", False


def fixed_rule_prohibition(text: str) -> str | None:
    prohibited_terms = (
        "電気工事",
        "医療行為",
        "介護",
        "送迎",
        "買い物代行",
        "高所作業",
        "危険工具",
        "チェーンソー",
        "金銭管理",
        "通帳",
        "暗証番号",
    )
    return next((term for term in prohibited_terms if term in text), None)


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


def reset_store() -> None:
    global requests_store, applications, matches, messages, reviews, achievements
    global profile_store, users_store, verifications, reports, blocks, idempotency_store
    profile_store = {
        "id": "usr_101",
        "displayName": "山田 花子",
        "role": "requester",
        "emailVerified": True,
        "verificationStatus": "approved",
        "areaCode": "AREA-001",
        "status": "active",
    }
    users_store = {
        profile_store["id"]: profile_store,
        "usr_207": {
            **HELPERS["usr_207"], "role": "helper", "status": "active",
            "emailVerified": True,
        },
        "usr_208": {
            **HELPERS["usr_208"], "role": "helper", "status": "active",
            "emailVerified": True,
        },
    }
    requests_store = {item["id"]: deepcopy(item) for item in INITIAL_REQUESTS}
    applications = {
        "app_55": {
            "id": "app_55",
            "requestId": "req_1024",
            "helperId": "usr_207",
            "message": "犬の散歩経験があります",
            "availableAt": "2026-08-19T17:00:00+09:00",
            "status": "applied",
            "createdAt": "2026-08-18T12:00:00+09:00",
        },
        "app_56": {
            "id": "app_56",
            "requestId": "req_1024",
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


def request_or_404(request_id: str) -> dict:
    return get_or_404(requests_store, request_id, "REQUEST_NOT_FOUND")


def match_or_404(match_id: str) -> dict:
    return get_or_404(matches, match_id, "MATCH_NOT_FOUND")


def ensure_match_participant(match: dict, user_id: str) -> str:
    if match["requesterId"] == user_id:
        return "requester"
    if match["helperId"] == user_id:
        return "helper"
    raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})


@app.post("/_mock/reset", tags=["Mock control"])
async def reset_mock():
    reset_store()
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
    prohibited_term = fixed_rule_prohibition(body.text)
    if prohibited_term:
        raise HTTPException(422, detail={"code": "PROHIBITED_REQUEST", "riskLevel": "prohibited"})
    last_category = "server"
    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            raw_result = await structure_generator(body)
            if isinstance(raw_result, str):
                raw_result = json.loads(raw_result)
            result = StructuredRequestOutput.model_validate(raw_result)
            return {
                **result.model_dump(),
                "mode": "ai",
                "attemptCount": attempt + 1,
                "requiresConfirmation": True,
            }
        except Exception as exc:
            category, retryable = classify_llm_failure(exc)
            last_category = category
            llm_failure_metrics[category] += 1
            logger.warning(
                "LLM structure failure category=%s attempt=%s retryable=%s",
                category,
                attempt + 1,
                retryable,
            )
            if not retryable or attempt >= MAX_LLM_RETRIES:
                break
            delay_seconds = (0.1 * (2**attempt)) + random.uniform(0, 0.05)
            await retry_sleeper(delay_seconds)

    llm_failure_metrics["fallback"] += 1
    return {
        "mode": "manual",
        "fallbackReason": last_category,
        "originalInput": {"text": body.text, "areaCode": body.areaCode},
        "manualForm": {
            "description": body.text,
            "areaCode": body.areaCode,
        },
        "requiresConfirmation": True,
        "autoPublished": False,
    }


@app.get("/requests", tags=["Requests"])
async def list_requests(
    category: str | None = None,
    areaCode: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    items = [item for item in requests_store.values() if item["status"] == "published"]
    if category:
        items = [item for item in items if item["category"] == category]
    if areaCode:
        items = [item for item in items if item["areaCode"] == areaCode]
    return {"items": items[:limit], "nextCursor": None}


@app.post("/requests", status_code=201, tags=["Requests"])
async def create_request(
    body: RequestInput,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    current_user: CurrentUser = Depends(get_current_user),
):
    if fixed_rule_prohibition(f"{body.title} {body.description} {body.category}"):
        raise HTTPException(
            422, detail={"code": "PROHIBITED_REQUEST", "riskLevel": "prohibited"}
        )
    cache_key = ("create_request", current_user.user_id, idempotency_key)
    if cache_key in idempotency_store:
        return idempotency_store[cache_key]
    request_id = new_id("req")
    item = {
        "id": request_id,
        "requesterId": current_user.user_id,
        **body.model_dump(exclude={"confirmed"}),
        "areaLabel": "大学周辺・約1km",
        "distanceKm": 1.0,
        "acceptedHelpers": 0,
        "status": "published",
        "version": 1,
        "warnings": [],
        "createdAt": now_iso(),
    }
    requests_store[request_id] = item
    idempotency_store[cache_key] = item
    return item


@app.get("/requests/{request_id}", tags=["Requests"])
async def get_request(request_id: str):
    return request_or_404(request_id)


@app.patch("/requests/{request_id}", tags=["Requests"])
async def update_request(
    request_id: str,
    body: RequestUpdateInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    item = request_or_404(request_id)
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
    item.update(changes)
    item["version"] += 1
    item["updatedAt"] = now_iso()
    return item


@app.delete("/requests/{request_id}", status_code=204, tags=["Requests"])
async def cancel_request(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    item = request_or_404(request_id)
    if item["requesterId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if item["status"] in {"completed", "cancelled"}:
        raise HTTPException(409, detail={"code": "INVALID_REQUEST_TRANSITION"})
    item["status"] = "cancelled"
    item["version"] += 1
    for application in applications.values():
        if application["requestId"] == request_id and application["status"] == "applied":
            application["status"] = "cancelled"
    return None


@app.get("/requests/{request_id}/applications", tags=["Applications"])
async def list_applications(
    request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    request_item = request_or_404(request_id)
    if request_item["requesterId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    return {
        "items": [
            {**item, "helper": HELPERS[item["helperId"]]}
            for item in applications.values()
            if item["requestId"] == request_id
        ]
    }


@app.post("/requests/{request_id}/applications", status_code=201, tags=["Applications"])
async def create_application(
    request_id: str,
    body: ApplicationInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    request_item = request_or_404(request_id)
    if request_item["status"] != "published":
        raise HTTPException(409, detail={"code": "REQUEST_NOT_OPEN"})
    if request_item["requesterId"] == current_user.user_id:
        raise HTTPException(403, detail={"code": "SELF_APPLICATION_NOT_ALLOWED"})
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
    request_item = request_or_404(body.requestId)
    if request_item["requesterId"] != current_user.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if request_item["version"] != body.expectedVersion:
        raise HTTPException(
            409,
            detail={"code": "REQUEST_STATE_CONFLICT", "currentVersion": request_item["version"]},
        )
    if application["status"] != "applied":
        raise HTTPException(409, detail={"code": "APPLICATION_NOT_SELECTABLE"})
    if request_item["acceptedHelpers"] >= request_item["requiredHelpers"]:
        raise HTTPException(409, detail={"code": "CAPACITY_REACHED"})
    application["status"] = "selected"
    request_item["acceptedHelpers"] += 1
    request_item["version"] += 1
    capacity_reached = request_item["acceptedHelpers"] >= request_item["requiredHelpers"]
    request_item["status"] = "matched" if capacity_reached else "matching"
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
    ensure_match_participant(match_or_404(match_id), current_user.user_id)
    return {"items": messages.get(match_id, []), "nextCursor": None}


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
    match[f"{actor_role}Confirmed"] = True
    if match["requesterConfirmed"] and match["helperConfirmed"]:
        match["status"] = "completed"
        match["completedAt"] = now_iso()
        request_or_404(match["requestId"])["status"] = "completed"
    else:
        match["status"] = "completion_pending"
        request_or_404(match["requestId"])["status"] = "completion_pending"
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
    request_or_404(match["requestId"])["status"] = "disputed"
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
    request_item = request_or_404(match["requestId"])
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
    if item["severity"] == "high" and body.targetType == "request":
        target = requests_store.get(body.targetId)
        if target:
            target["status"] = "suspended"
            target["version"] += 1
    return item


@app.post("/users/{user_id}/block", status_code=201, tags=["Safety"])
async def set_user_block(
    user_id: str,
    body: BlockInput,
    current_user: CurrentUser = Depends(get_current_user),
):
    if user_id == current_user.user_id:
        raise HTTPException(422, detail={"code": "SELF_BLOCK_NOT_ALLOWED"})
    if body.blocked:
        blocks.add(user_id)
    else:
        blocks.discard(user_id)
    return {"userId": user_id, "blocked": user_id in blocks, "updatedAt": now_iso()}
