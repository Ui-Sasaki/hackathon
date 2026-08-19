from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from app.routers import system_router
from app.schemas import (
    AchievementInput, AchievementVisibilityInput, ApplicationInput, AuthInput,
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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(system_router)


ERROR_MESSAGES = {
    "REQUEST_NOT_FOUND": "依頼が見つかりません",
    "MATCH_NOT_FOUND": "マッチが見つかりません",
    "APPLICATION_NOT_FOUND": "応募が見つかりません",
    "REQUEST_STATE_CONFLICT": "依頼の状態が更新されているため処理できません",
    "VALIDATION_ERROR": "入力内容を確認してください",
}


def error_body(code: str, details: dict[str, Any] | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": ERROR_MESSAGES.get(code, code.replace("_", " ").lower()),
            "details": details or {},
            "requestId": new_id("trace"),
        }
    }


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    code = detail.pop("code", "HTTP_ERROR")
    return JSONResponse(status_code=exc.status_code, content=error_body(code, detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(error_body("VALIDATION_ERROR", {"errors": exc.errors()})),
    )


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
    global profile_store, verifications, reports, blocks, idempotency_store
    profile_store = {
        "id": "usr_101",
        "displayName": "山田 花子",
        "role": "requester",
        "emailVerified": True,
        "verificationStatus": "approved",
        "areaCode": "AREA-001",
        "status": "active",
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


def request_or_404(request_id: str) -> dict:
    return get_or_404(requests_store, request_id, "REQUEST_NOT_FOUND")


def match_or_404(match_id: str) -> dict:
    return get_or_404(matches, match_id, "MATCH_NOT_FOUND")


@app.post("/_mock/reset", tags=["Mock control"])
def reset_mock():
    reset_store()
    return {"reset": True}


@app.post("/auth/register", status_code=201, tags=["Auth"])
def register(body: AuthInput):
    return {
        "user": {**profile_store, "emailVerified": False},
        "session": {"type": "mock_cookie", "expiresIn": 3600},
    }


@app.post("/auth/login", tags=["Auth"])
def login(_body: AuthInput):
    return {"user": profile_store, "session": {"type": "mock_cookie", "expiresIn": 3600}}


@app.post("/auth/logout", status_code=204, tags=["Auth"])
def logout():
    return None


@app.get("/profile", tags=["Profile"])
def get_profile():
    return profile_store


@app.patch("/profile", tags=["Profile"])
def update_profile(body: ProfileUpdateInput):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(422, detail={"code": "NO_CHANGES"})
    profile_store.update(changes)
    profile_store["updatedAt"] = now_iso()
    return profile_store


@app.post("/requests/structure", tags=["Requests"])
def structure_request(body: StructureInput):
    if any(word in body.text for word in ["電気工事", "医療行為", "介護", "送迎"]):
        raise HTTPException(422, detail={"code": "PROHIBITED_REQUEST", "riskLevel": "prohibited"})
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


@app.get("/requests", tags=["Requests"])
def list_requests(
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
def create_request(body: RequestInput, idempotency_key: str = Header(alias="Idempotency-Key")):
    cache_key = ("create_request", idempotency_key)
    if cache_key in idempotency_store:
        return idempotency_store[cache_key]
    request_id = new_id("req")
    item = {
        "id": request_id,
        "requesterId": "usr_101",
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
def get_request(request_id: str):
    return request_or_404(request_id)


@app.patch("/requests/{request_id}", tags=["Requests"])
def update_request(request_id: str, body: RequestUpdateInput):
    item = request_or_404(request_id)
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
def cancel_request(request_id: str):
    item = request_or_404(request_id)
    if item["status"] in {"completed", "cancelled"}:
        raise HTTPException(409, detail={"code": "INVALID_REQUEST_TRANSITION"})
    item["status"] = "cancelled"
    item["version"] += 1
    for application in applications.values():
        if application["requestId"] == request_id and application["status"] == "applied":
            application["status"] = "cancelled"
    return None


@app.get("/requests/{request_id}/applications", tags=["Applications"])
def list_applications(request_id: str):
    request_or_404(request_id)
    return {
        "items": [
            {**item, "helper": HELPERS[item["helperId"]]}
            for item in applications.values()
            if item["requestId"] == request_id
        ]
    }


@app.post("/requests/{request_id}/applications", status_code=201, tags=["Applications"])
def create_application(request_id: str, body: ApplicationInput):
    request_item = request_or_404(request_id)
    if request_item["status"] != "published":
        raise HTTPException(409, detail={"code": "REQUEST_NOT_OPEN"})
    if request_item["requesterId"] == "usr_207":
        raise HTTPException(403, detail={"code": "SELF_APPLICATION_NOT_ALLOWED"})
    if any(
        item["requestId"] == request_id
        and item["helperId"] == "usr_207"
        and item["status"] not in {"withdrawn", "cancelled"}
        for item in applications.values()
    ):
        raise HTTPException(409, detail={"code": "DUPLICATE_APPLICATION"})
    item = {
        "id": new_id("app"),
        "requestId": request_id,
        "helperId": "usr_207",
        **body.model_dump(),
        "status": "applied",
        "createdAt": now_iso(),
    }
    applications[item["id"]] = item
    return item


@app.post("/applications/{application_id}/withdraw", tags=["Applications"])
def withdraw_application(application_id: str):
    application = applications.get(application_id)
    if not application:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    if application["status"] != "applied":
        raise HTTPException(409, detail={"code": "APPLICATION_NOT_WITHDRAWABLE"})
    application["status"] = "withdrawn"
    application["updatedAt"] = now_iso()
    return application


@app.post("/applications/{application_id}/select", status_code=201, tags=["Applications"])
def select_application(application_id: str, body: SelectionInput):
    application = applications.get(application_id)
    if not application:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    if application["requestId"] != body.requestId:
        raise HTTPException(409, detail={"code": "APPLICATION_REQUEST_MISMATCH"})
    request_item = request_or_404(body.requestId)
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
def get_match(match_id: str):
    return match_or_404(match_id)


@app.get("/matches/{match_id}/messages", tags=["Messages"])
def list_messages(match_id: str):
    match_or_404(match_id)
    return {"items": messages.get(match_id, []), "nextCursor": None}


@app.post("/matches/{match_id}/messages", status_code=201, tags=["Messages"])
def create_message(match_id: str, body: MessageInput):
    match_or_404(match_id)
    item = {
        "id": new_id("msg"),
        "matchId": match_id,
        "senderId": "usr_101",
        "body": body.body,
        "sentAt": now_iso(),
        "readAt": None,
        "moderationStatus": "allowed",
    }
    messages.setdefault(match_id, []).append(item)
    return item


@app.post("/matches/{match_id}/complete", tags=["Matches"])
def complete_match(match_id: str, body: CompletionInput):
    match = match_or_404(match_id)
    match[f"{body.actorRole}Confirmed"] = True
    if match["requesterConfirmed"] and match["helperConfirmed"]:
        match["status"] = "completed"
        match["completedAt"] = now_iso()
        request_or_404(match["requestId"])["status"] = "completed"
    else:
        match["status"] = "completion_pending"
        request_or_404(match["requestId"])["status"] = "completion_pending"
    return match


@app.post("/matches/{match_id}/dispute", tags=["Matches"])
def dispute_match(match_id: str, body: DisputeInput):
    match = match_or_404(match_id)
    if match["status"] in {"completed", "disputed"}:
        raise HTTPException(409, detail={"code": "MATCH_NOT_DISPUTABLE"})
    match.update({"status": "disputed", "disputeReason": body.reason, "disputedAt": now_iso()})
    request_or_404(match["requestId"])["status"] = "disputed"
    return match


@app.post("/matches/{match_id}/reviews", status_code=201, tags=["Reviews"])
def create_review(match_id: str, body: ReviewInput):
    match = match_or_404(match_id)
    if match["status"] != "completed":
        raise HTTPException(409, detail={"code": "MATCH_NOT_COMPLETED"})
    if any(
        review["matchId"] == match_id and review["reviewerId"] == "usr_101"
        for review in reviews.values()
    ):
        raise HTTPException(409, detail={"code": "DUPLICATE_REVIEW"})
    item = {
        "id": new_id("review"),
        "matchId": match_id,
        "reviewerId": "usr_101",
        "revieweeId": match["helperId"],
        **body.model_dump(),
        "createdAt": now_iso(),
    }
    reviews[item["id"]] = item
    return item


@app.post("/achievements/generate", status_code=201, tags=["Achievements"])
def generate_achievement(body: AchievementInput):
    match = match_or_404(body.matchId)
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
def update_achievement_visibility(body: AchievementVisibilityInput):
    item = achievements.get(body.achievementId)
    if not item:
        raise HTTPException(404, detail={"code": "ACHIEVEMENT_NOT_FOUND"})
    if body.visibility == "public" and not body.approved:
        raise HTTPException(409, detail={"code": "ACHIEVEMENT_APPROVAL_REQUIRED"})
    item["visibility"] = body.visibility
    if body.approved:
        item["approvedAt"] = now_iso()
        item["status"] = "approved"
    return item


@app.post("/verifications", status_code=201, tags=["Verification"])
def create_verification(body: VerificationInput):
    if body.method == "student_card" and not body.storageObjectKey:
        raise HTTPException(422, detail={"code": "STORAGE_OBJECT_REQUIRED"})
    if any(item["status"] == "pending" for item in verifications.values()):
        raise HTTPException(409, detail={"code": "VERIFICATION_ALREADY_PENDING"})
    item = {
        "id": new_id("verification"),
        "userId": "usr_101",
        **body.model_dump(),
        "status": "pending",
        "createdAt": now_iso(),
    }
    verifications[item["id"]] = item
    profile_store["verificationStatus"] = "pending"
    return item


@app.post("/reports", status_code=201, tags=["Safety"])
def create_report(body: ReportInput):
    item = {
        "id": new_id("report"),
        "reporterId": "usr_101",
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
def set_user_block(user_id: str, body: BlockInput):
    if user_id == "usr_101":
        raise HTTPException(422, detail={"code": "SELF_BLOCK_NOT_ALLOWED"})
    if body.blocked:
        blocks.add(user_id)
    else:
        blocks.discard(user_id)
    return {"userId": user_id, "blocked": user_id in blocks, "updatedAt": now_iso()}
