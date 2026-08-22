from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


LocationFailure = Literal["denied", "timeout", "unsupported", "unavailable"]


class LocationResolveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consentGranted: bool = False
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    failureReason: LocationFailure | None = None

    @model_validator(mode="after")
    def validate_location_result(self) -> "LocationResolveInput":
        has_coordinates = self.latitude is not None or self.longitude is not None
        if has_coordinates and (
            self.latitude is None or self.longitude is None or not self.consentGranted
        ):
            raise ValueError("coordinates require consent and must be provided together")
        if self.consentGranted and not has_coordinates and self.failureReason is None:
            raise ValueError("consent requires coordinates or a failure reason")
        if has_coordinates and self.failureReason is not None:
            raise ValueError("failureReason cannot be combined with coordinates")
        return self


class StructureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=5, max_length=3000)
    areaCode: str | None = Field(default=None, min_length=1, max_length=30)
    location: LocationResolveInput | None = None


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
