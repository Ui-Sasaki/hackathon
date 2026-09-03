"""Public API contracts used by runtime validation and OpenAPI."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

LocationFailure = Literal["denied", "timeout", "unsupported", "unavailable"]
RequestStatus = Literal["draft", "pending_review", "published", "matching", "matched", "in_progress", "completion_pending", "completed", "rejected", "cancelled", "expired", "suspended", "disputed"]
ApplicationStatus = Literal["applied", "selected", "accepted", "completed", "not_selected", "withdrawn", "cancelled"]
MatchStatus = Literal["matched", "in_progress", "completion_pending", "completed", "disputed"]
VerificationStatus = Literal["unverified", "pending", "approved", "rejected", "expired"]
UploadPurpose = Literal["profile_image", "verification_document"]
RiskLevel = Literal["low", "medium", "high", "prohibited"]
SafetyDecision = Literal["publish", "publish_with_warning", "pending_review", "rejected"]
SafetyLLMStatus = Literal["ok", "skipped_fixed_rule", "skipped_not_configured", "unavailable", "invalid_output"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ErrorDetail(ContractModel):
    code: str = Field(description="クライアント判定用のUPPER_SNAKE_CASEコード")
    message: str = Field(description="利用者向けの安全なメッセージ")
    details: dict[str, Any] = Field(default_factory=dict, description="安全に公開できる追加情報")
    requestId: str = Field(description="X-Request-IDと一致するトレースID")


class ErrorResponse(ContractModel):
    error: ErrorDetail


class LocationResolveInput(ContractModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"consentGranted": True, "latitude": 43.082, "longitude": 141.350}]})
    consentGranted: bool = Field(False, description="現在地利用への明示的な同意")
    latitude: float | None = Field(None, ge=-90, le=90, description="同意時だけ送る緯度。保存・返却しない")
    longitude: float | None = Field(None, ge=-180, le=180, description="同意時だけ送る経度。保存・返却しない")
    failureReason: LocationFailure | None = Field(None, description="位置取得失敗理由")

    @model_validator(mode="after")
    def validate_location_result(self) -> "LocationResolveInput":
        has_coordinates = self.latitude is not None or self.longitude is not None
        if has_coordinates and (self.latitude is None or self.longitude is None or not self.consentGranted):
            raise ValueError("coordinates require consent and must be provided together")
        if self.consentGranted and not has_coordinates and self.failureReason is None:
            raise ValueError("consent requires coordinates or a failure reason")
        if has_coordinates and self.failureReason is not None:
            raise ValueError("failureReason cannot be combined with coordinates")
        return self


class LocationResolveResponse(ContractModel):
    areaCode: str = Field(description="概算地域コード")
    areaLabel: str = Field(description="表示用の概算地域名")
    source: Literal["current_location", "selected_region", "registered_region"]
    fallbackUsed: bool


class StructureInput(ContractModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"text": "病気なので小型犬の散歩をお願いしたい", "areaCode": "AREA-001"}]})
    text: str = Field(min_length=5, max_length=3000, description="個人情報を含めない依頼文")
    areaCode: str | None = Field(None, min_length=1, max_length=30)
    location: LocationResolveInput | None = None
    maskingConfirmed: bool = False


class MaskingDetection(ContractModel):
    type: str
    placeholder: str
    count: int = Field(ge=1)


class MaskingConfirmationResponse(ContractModel):
    maskedText: str
    detections: list[MaskingDetection]
    hasDetections: bool
    ruleVersion: str
    status: Literal["masking_confirmation_required"]
    requiresMaskingConfirmation: Literal[True]
    message: str


ShortExtractedText = Annotated[str, Field(min_length=1, max_length=200)]
MissingFieldCode = Literal[
    "title", "description", "category", "scheduledAt", "estimatedMinutes",
    "approximateArea", "requiredHelpers", "itemsToBring", "details",
]


class StructuredRequestDraft(ContractModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=50)
    scheduledAt: datetime | None = Field(default=None, description="ISO 8601日時")
    estimatedMinutes: int | None = Field(default=None, ge=10, le=240)
    approximateArea: str | None = Field(default=None, max_length=100)
    requiredHelpers: int | None = Field(default=None, ge=1, le=5)
    itemsToBring: list[ShortExtractedText] = Field(max_length=20)
    riskLevel: Literal["low", "medium", "high", "prohibited"]
    riskCandidates: list[ShortExtractedText] = Field(max_length=20)
    missingFields: list[MissingFieldCode] = Field(max_length=20)
    warnings: list[ShortExtractedText] = Field(max_length=20)

class AppliedMasking(ContractModel):
    detections: list[MaskingDetection]
    ruleVersion: str
    confirmed: bool


class StructureMetadata(ContractModel):
    modelName: str
    promptVersion: str
    processedAt: datetime


class VoiceRequestData(ContractModel):
    task: str
    location: str | None = None
    duration: str | None = None
    deadline: str | None = None
    notes: str | None = None

class SafetyAssessment(ContractModel):
    """固定ルールとLLMを併用した危険度判定の結果と、その判定根拠。"""

    riskLevel: RiskLevel = Field(description="固定ルールとLLMのうち強い方を採用した最終危険度")
    decision: SafetyDecision = Field(description="公開可否の決定")
    reasonCodes: list[str] = Field(default_factory=list, description="判定理由のコード")
    messages: list[str] = Field(default_factory=list, description="利用者向けの安全なメッセージ")
    matchedRules: list[str] = Field(default_factory=list, description="一致した固定ルールのコード")
    ruleVersion: str = Field(description="固定ルールの版")
    promptVersion: str = Field(description="LLMプロンプトの版")
    model: str | None = Field(None, description="判定に使ったモデル名")
    llmLevel: RiskLevel | None = Field(None, description="LLM単独の判定。固定ルールを緩める用途には使わない")
    llmStatus: SafetyLLMStatus = Field(description="LLM判定の実行結果")
    evaluatedAt: str = Field(description="判定日時（ISO 8601、UTC）")


class StructuredRequestResponse(StructuredRequestDraft):
    masking: AppliedMasking
    status: Literal["draft"]
    requiresConfirmation: Literal[True]
    autoPublished: Literal[False]
    additionalQuestion: str | None = None
    metadata: StructureMetadata
    request: VoiceRequestData = Field(description="音声入力画面との互換用依頼データ")
    safety: SafetyAssessment = Field(description="公開前の危険度判定結果")


class RequestInput(ContractModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"title": "庭の片付け", "description": "庭の落ち葉を一緒に片付けてください", "category": "cleaning", "scheduledAt": "2026-08-22T10:00:00+09:00", "estimatedMinutes": 30, "requiredHelpers": 1, "areaCode": "AREA-001", "riskLevel": "low", "confirmed": True}]})
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=100)
    scheduledAt: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$", description="ISO 8601、タイムゾーン付き")
    estimatedMinutes: int = Field(ge=10, le=240)
    requiredHelpers: int = Field(1, ge=1, le=5)
    areaCode: str = Field(min_length=1, max_length=30, description="概算地域コード")
    riskLevel: Literal["low", "medium"] = "low"
    confirmed: Literal[True] = Field(description="利用者が内容を確認済み")


class RequestResponse(ContractModel):
    id: str
    requesterId: str
    title: str
    description: str
    category: str
    riskLevel: Literal["low", "medium", "high", "prohibited"]
    areaCode: str
    areaLabel: str
    distanceKm: float | None = Field(None, ge=0, description="概算距離")
    acceptedHelpers: int = Field(ge=0)
    scheduledAt: datetime
    estimatedMinutes: int = Field(ge=10, le=240)
    requiredHelpers: int = Field(ge=1, le=5)
    status: RequestStatus
    version: int = Field(ge=1, description="楽観ロック値")
    warnings: list[str]
    createdAt: datetime
    updatedAt: datetime


class ListOrigin(ContractModel):
    areaCode: str
    source: Literal["current_location", "selected_region", "registered_region"]


class RequestListResponse(ContractModel):
    items: list[RequestResponse]
    nextCursor: str | None = Field(description="次ページなしの場合null")
    origin: ListOrigin


class SavedRequestListResponse(ContractModel):
    items: list[RequestResponse]


class RequestUpdateInput(ContractModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=2000)
    scheduledAt: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$")
    estimatedMinutes: int | None = Field(None, ge=10, le=240)
    requiredHelpers: int | None = Field(None, ge=1, le=5)
    expectedVersion: int = Field(ge=1)


class ProfileUpdateInput(ContractModel):
    displayName: str | None = Field(None, min_length=1, max_length=50)
    areaCode: str | None = Field(None, min_length=1, max_length=30)
    region: str | None = Field(None, min_length=1, max_length=20)
    age: str | None = Field(None, min_length=1, max_length=30)
    notes: str | None = Field(None, max_length=500)
    helperType: Literal["student", "worker"] | None = None
    university: str | None = Field(None, min_length=1, max_length=100)
    faculty: str | None = Field(None, min_length=1, max_length=100)
    schoolYear: str | None = Field(None, min_length=1, max_length=30)
    occupation: str | None = Field(None, min_length=1, max_length=100)
    industry: str | None = Field(None, max_length=100)
    workplace: str | None = Field(None, max_length=100)
    gender: str | None = Field(None, max_length=30)
    interest: str | None = Field(None, max_length=200)
    message: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_helper_details(self) -> "ProfileUpdateInput":
        if self.helperType == "student" and not all(
            (self.university, self.faculty, self.schoolYear)
        ):
            raise ValueError("student helper details are required")
        if self.helperType == "worker" and not self.occupation:
            raise ValueError("worker occupation is required")
        return self


class ProfileResponse(ContractModel):
    id: str
    displayName: str = Field(max_length=50)
    role: Literal["member", "admin", "verifier"]
    emailVerified: bool
    verificationStatus: VerificationStatus
    areaCode: str | None = None
    region: str | None = None
    age: str | None = None
    notes: str | None = None
    helperType: Literal["student", "worker"] | None = None
    university: str | None = None
    faculty: str | None = None
    schoolYear: str | None = None
    occupation: str | None = None
    industry: str | None = None
    workplace: str | None = None
    gender: str | None = None
    interest: str | None = None
    message: str | None = None
    status: Literal["active", "suspended"]
    imageUrl: str | None = Field(None, description="プロフィール画像の表示用URL。未設定ならnull")
    updatedAt: datetime | None = None


class UploadSessionInput(ContractModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"purpose": "profile_image", "contentType": "image/jpeg", "byteSize": 240000, "fileName": "photo.jpg"}]})
    purpose: UploadPurpose = Field(description="画像の用途")
    contentType: str = Field(min_length=1, max_length=100, description="申告するMIME type。対応外は415。受信時に実体と突き合わせる")
    byteSize: int = Field(ge=1, description="申告するファイルサイズ。上限超過は413")
    fileName: str | None = Field(None, max_length=200, description="拡張子の突き合わせだけに使う。保存はしない")


class UploadSessionResponse(ContractModel):
    uploadId: str = Field(description="アップロードの識別子。ストレージ内部キーではない")
    uploadUrl: str = Field(description="本文を送る先。期限付きで、この利用者だけが使える")
    expiresAt: str = Field(description="アップロードの期限（ISO 8601、UTC）")
    maxBytes: int = Field(description="受け付ける最大バイト数")


class UploadedContentResponse(ContractModel):
    uploadId: str
    status: Literal["stored"]
    contentType: Literal["image/jpeg", "image/png"]
    byteSize: int = Field(description="メタデータ除去後のバイト数")


class ProfileImageInput(ContractModel):
    uploadId: str = Field(min_length=1, max_length=100, description="本文の送信を終えたアップロードの識別子")


class ProfileImageResponse(ContractModel):
    imageId: str
    imageUrl: str = Field(description="表示用の推測できないURL。ストレージ内部キーは含まない")
    updatedAt: datetime
class UserSettingsUpdateInput(ContractModel):
    model_config = ConfigDict(extra="forbid")
    notificationsEnabled: StrictBool | None = None
    locationEnabled: StrictBool | None = None
    fontSize: Literal["small", "medium", "large"] | None = None


class UserSettingsResponse(ContractModel):
    notificationsEnabled: bool
    locationEnabled: bool
    fontSize: Literal["small", "medium", "large"]


class ApplicationInput(ContractModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"message": "犬の散歩経験があります", "availableAt": "2026-08-19T17:00:00+09:00"}]})
    message: str = Field(min_length=1, max_length=1000)
    availableAt: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$")


class ApplicationResponse(ContractModel):
    id: str
    requestId: str
    helperId: str
    message: str
    availableAt: datetime
    status: ApplicationStatus
    createdAt: datetime
    updatedAt: datetime | None = None


class HelperSummary(ContractModel):
    id: str
    displayName: str
    verificationStatus: VerificationStatus
    universityVerified: bool
    skillTags: list[str]
    achievementCount: int = Field(ge=0)


class ApplicationWithHelperResponse(ApplicationResponse):
    helper: HelperSummary


class ApplicationListResponse(ContractModel):
    items: list[ApplicationWithHelperResponse]


class SelectionInput(ContractModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(ge=1)


class MatchResponse(ContractModel):
    id: str
    requestId: str
    requesterId: str
    helperId: str
    status: MatchStatus
    requesterConfirmed: bool
    helperConfirmed: bool
    matchedAt: datetime
    completedAt: datetime | None
    disputeReason: str | None = None
    disputedAt: datetime | None = None
    version: int = Field(ge=1)


class MessageInput(ContractModel):
    body: str = Field(min_length=1, max_length=2000)
    # --- 送信確認フロー（別パターン）有効化時にコメントアウトを外す ---
    # confirmed: bool = Field(False, description="警告が出たメッセージの送信を強制するフラグ")


class MessageResponse(ContractModel):
    id: str
    matchId: str
    senderId: str
    body: str
    sentAt: datetime
    readAt: datetime | None
    moderationStatus: Literal["allowed", "flagged", "hidden"]


class MessageListResponse(ContractModel):
    items: list[MessageResponse]
    nextCursor: str | None = Field(description="次ページなしの場合null。現行実装は常にnull")


class CompletionInput(ContractModel):
    completed: Literal[True]
    actorRole: Literal["requester", "helper"]


class DisputeInput(ContractModel):
    reason: str = Field(min_length=10, max_length=1000)


class ReviewInput(ContractModel):
    onTime: bool
    polite: bool
    safetyAware: bool
    communicative: bool
    comment: str = Field(min_length=1, max_length=1000)


class ReviewResponse(ReviewInput):
    id: str
    matchId: str
    reviewerId: str
    revieweeId: str
    createdAt: datetime


class AchievementInput(ContractModel):
    matchId: str
    visibility: Literal["private", "members", "public"] = "members"


class AchievementFacts(ContractModel):
    category: str
    minutes: int = Field(ge=0)


class AchievementResponse(ContractModel):
    id: str
    userId: str
    matchId: str
    generatedText: str
    facts: AchievementFacts
    visibility: Literal["private", "members", "public"]
    status: Literal["generated", "approved"]
    modelName: str
    promptVersion: str
    generatedAt: datetime
    approvedAt: datetime | None


class AchievementVisibilityInput(ContractModel):
    achievementId: str
    visibility: Literal["private", "members", "public"]
    approved: bool = False


class VerificationInput(ContractModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"method": "student_card", "uploadId": "4f1c0f0e-0f1e-4f4a-9b2a-2f1d3c4b5a60"}]})
    method: Literal["university_email", "student_card"]
    uploadId: str | None = Field(None, min_length=1, max_length=100, description="学生証方式のみ。用途 verification_document のアップロード識別子。ストレージ内部キーは受け取らない")


class VerificationResponse(ContractModel):
    id: str
    userId: str
    method: Literal["university_email", "student_card"]
    status: VerificationStatus
    createdAt: datetime


class ReportInput(ContractModel):
    targetType: Literal["user", "request", "match", "message", "review"]
    targetId: str = Field(min_length=1, max_length=100)
    reason: Literal["fraud", "harassment", "dangerous_work", "false_information", "no_show", "personal_information_request", "payment_request", "other"]
    description: str = Field(min_length=10, max_length=2000)


class ReportResponse(ContractModel):
    id: str
    reporterId: str
    targetType: Literal["user", "request", "match", "message", "review"]
    targetId: str
    reason: str
    description: str
    severity: Literal["medium", "high"]
    status: Literal["open", "resolved"]
    createdAt: datetime


class BlockInput(ContractModel):
    blocked: bool = True


class BlockResponse(ContractModel):
    userId: str
    blocked: bool
    updatedAt: datetime


class ResetResponse(ContractModel):
    reset: Literal[True]


class AuthInput(ContractModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)

class RecommendedRequestItem(ContractModel):
    request: RequestResponse
    score: int = Field(ge=0, le=100, description="推薦総合スコア(0-100)")
    reason: str = Field(description="ユーザーに提示する推薦理由")

class RecommendedRequestListResponse(ContractModel):
    items: list[RecommendedRequestItem]
    nextCursor: str | None = Field(description="次ページなしの場合null")
