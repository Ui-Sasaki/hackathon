from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StructureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=5, max_length=3000)
    areaCode: str
    maskingConfirmed: bool = False


ShortExtractedText = Annotated[str, Field(min_length=1, max_length=200)]
MissingFieldCode = Literal[
    "title",
    "description",
    "category",
    "scheduledAt",
    "estimatedMinutes",
    "approximateArea",
    "requiredHelpers",
    "itemsToBring",
    "details",
]


class StructuredRequestDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=50)
    scheduledAt: str | None = None
    estimatedMinutes: int | None = Field(default=None, ge=10, le=240)
    approximateArea: str = Field(min_length=1, max_length=100)
    requiredHelpers: int | None = Field(default=None, ge=1, le=5)
    itemsToBring: list[ShortExtractedText] = Field(max_length=20)
    warnings: list[ShortExtractedText] = Field(max_length=20)
    riskCandidates: list[ShortExtractedText] = Field(max_length=20)
    missingFields: list[MissingFieldCode] = Field(max_length=20)


class StructureMetadata(BaseModel):
    modelName: str
    promptVersion: str
    processedAt: str


class StructuredRequestResponse(StructuredRequestDraft):
    status: Literal["draft"]
    requiresConfirmation: Literal[True]
    autoPublished: Literal[False]
    additionalQuestion: str | None = None
    metadata: StructureMetadata


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
        "fraud", "harassment", "dangerous_work", "false_information", "no_show",
        "personal_information_request", "payment_request", "other",
    ]
    description: str = Field(min_length=10, max_length=2000)


class ProfileUpdateInput(BaseModel):
    displayName: str | None = Field(default=None, min_length=1, max_length=50)
    areaCode: str | None = Field(default=None, min_length=1, max_length=30)


class RequestUpdateInput(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    scheduledAt: str | None = None
    estimatedMinutes: int | None = Field(default=None, ge=10, le=240)
    requiredHelpers: int | None = Field(default=None, ge=1, le=5)
    expectedVersion: int = Field(ge=1)


class DisputeInput(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class AchievementVisibilityInput(BaseModel):
    achievementId: str
    visibility: Literal["private", "members", "public"]
    approved: bool = False


class VerificationInput(BaseModel):
    method: Literal["university_email", "student_card"]
    storageObjectKey: str | None = Field(default=None, max_length=300)


class BlockInput(BaseModel):
    blocked: bool = True


class AuthInput(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)
