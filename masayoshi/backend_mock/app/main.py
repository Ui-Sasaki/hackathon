from copy import deepcopy
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


class StructureInput(BaseModel):
    text: str = Field(min_length=5, max_length=3000)
    areaCode: str


class RequestInput(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    category: str
    scheduledAt: str
    estimatedMinutes: int = Field(ge=10, le=240)
    requiredHelpers: int = Field(default=1, ge=1, le=5)
    areaCode: str
    riskLevel: Literal["low", "medium"] = "low"
    confirmed: Literal[True]


class ApplicationInput(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    availableAt: str


class SelectionInput(BaseModel):
    requestId: str
    expectedVersion: int = Field(ge=1)


class MessageInput(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CompletionInput(BaseModel):
    completed: Literal[True]
    actorRole: Literal["requester", "helper"]


class ReviewInput(BaseModel):
    onTime: bool
    polite: bool
    safetyAware: bool
    communicative: bool
    comment: str = Field(min_length=1, max_length=1000)


class AchievementInput(BaseModel):
    matchId: str
    visibility: Literal["private", "members", "public"] = "members"


class ReportInput(BaseModel):
    targetType: Literal["user", "request", "match", "message", "review"]
    targetId: str
    reason: Literal[
        "fraud",
        "harassment",
        "dangerous_work",
        "false_information",
        "no_show",
        "personal_information_request",
        "payment_request",
        "other",
    ]
    description: str = Field(min_length=10, max_length=2000)


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


reset_store()


def request_or_404(request_id: str) -> dict:
    if request_id not in requests_store:
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    return requests_store[request_id]


def match_or_404(match_id: str) -> dict:
    if match_id not in matches:
        raise HTTPException(404, detail={"code": "MATCH_NOT_FOUND"})
    return matches[match_id]


@app.get("/", tags=["System"])
def root():
    return {"name": app.title, "version": app.version, "docs": "/docs"}


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "time": now_iso()}


@app.post("/_mock/reset", tags=["Mock control"])
def reset_mock():
    reset_store()
    return {"reset": True}


@app.get("/profile", tags=["Profile"])
def get_profile():
    return {
        "id": "usr_101",
        "displayName": "山田 花子",
        "role": "requester",
        "verificationStatus": "approved",
        "areaCode": "AREA-001",
    }


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
    return item


@app.get("/requests/{request_id}", tags=["Requests"])
def get_request(request_id: str):
    return request_or_404(request_id)


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


@app.post("/applications/{application_id}/select", status_code=201, tags=["Applications"])
def select_application(application_id: str, body: SelectionInput):
    application = applications.get(application_id)
    if not application:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    request_item = request_or_404(body.requestId)
    if request_item["version"] != body.expectedVersion:
        raise HTTPException(
            409,
            detail={"code": "REQUEST_STATE_CONFLICT", "currentVersion": request_item["version"]},
        )
    if request_item["acceptedHelpers"] >= request_item["requiredHelpers"]:
        raise HTTPException(409, detail={"code": "CAPACITY_REACHED"})
    application["status"] = "selected"
    request_item["acceptedHelpers"] += 1
    request_item["version"] += 1
    request_item["status"] = "matched"
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
    else:
        match["status"] = "completion_pending"
    return match


@app.post("/matches/{match_id}/reviews", status_code=201, tags=["Reviews"])
def create_review(match_id: str, body: ReviewInput):
    match = match_or_404(match_id)
    if match["status"] != "completed":
        raise HTTPException(409, detail={"code": "MATCH_NOT_COMPLETED"})
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


@app.post("/reports", status_code=201, tags=["Safety"])
def create_report(body: ReportInput):
    return {
        "id": new_id("report"),
        "reporterId": "usr_101",
        **body.model_dump(),
        "severity": "high" if body.reason in {"fraud", "dangerous_work"} else "medium",
        "status": "open",
        "createdAt": now_iso(),
    }
