"""本人確認審査のRepository境界と開発・テスト用Memory実装。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol

from app.auth import CurrentUser
from app.settings import settings

ReviewDecision = Literal["approved", "rejected"]


class VerificationReviewRepositoryError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class VerificationReviewRepository(Protocol):
    async def list_pending(self) -> list[dict[str, Any]]: ...

    async def get(self, verification_id: str) -> dict[str, Any] | None: ...

    async def decide(
        self, verification_id: str, reviewer: CurrentUser, decision: ReviewDecision
    ) -> dict[str, Any]: ...

    async def mark_document_deleted(
        self, verification_id: str, actor: CurrentUser
    ) -> dict[str, Any]: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class MemoryVerificationReviewRepository:
    async def list_pending(self) -> list[dict[str, Any]]:
        from app.cruds import main as runtime

        return [deepcopy(item) for item in runtime.verifications.values()
                if item["status"] == "pending"]

    async def get(self, verification_id: str) -> dict[str, Any] | None:
        from app.cruds import main as runtime

        item = runtime.verifications.get(verification_id)
        return deepcopy(item) if item else None

    async def decide(
        self, verification_id: str, reviewer: CurrentUser, decision: ReviewDecision
    ) -> dict[str, Any]:
        from app.cruds import main as runtime

        item = runtime.verifications.get(verification_id)
        if item is None:
            raise VerificationReviewRepositoryError("VERIFICATION_NOT_FOUND")
        if item["status"] != "pending":
            raise VerificationReviewRepositoryError("VERIFICATION_STATE_CONFLICT")
        now = _now()
        item.update({
            "status": decision,
            "reviewerId": reviewer.user_id,
            "reviewedAt": _iso(now),
            "deletionDueAt": _iso(now + timedelta(days=7))
            if item.get("_imageId") else None,
        })
        runtime.users_store[item["userId"]]["verificationStatus"] = decision
        runtime.record_audit_event(
            actor_id=reviewer.user_id,
            event_type=f"verification_{decision}",
            target_type="verification_request",
            target_id=verification_id,
        )
        return deepcopy(item)

    async def mark_document_deleted(
        self, verification_id: str, actor: CurrentUser
    ) -> dict[str, Any]:
        from app.cruds import main as runtime

        item = runtime.verifications.get(verification_id)
        if item is None:
            raise VerificationReviewRepositoryError("VERIFICATION_NOT_FOUND")
        if item["status"] == "pending":
            raise VerificationReviewRepositoryError("VERIFICATION_STATE_CONFLICT")
        if not item.get("_imageId") or item.get("deletedAt"):
            raise VerificationReviewRepositoryError("VERIFICATION_DOCUMENT_NOT_FOUND")
        item["deletedAt"] = runtime.now_iso()
        runtime.record_audit_event(
            actor_id=actor.user_id,
            event_type="verification_document_deleted",
            target_type="verification_request",
            target_id=verification_id,
        )
        return deepcopy(item)


_memory = MemoryVerificationReviewRepository()


def get_verification_review_repository() -> VerificationReviewRepository:
    # Postgresの暫定実装へ誤ってフォールバックし、審査結果をプロセス内だけに
    # 保存する事故を防ぐ。本番実装はSupabase担当との合意後に追加する。
    if settings.request_repository != "memory":
        raise RuntimeError("verification review repository is not configured")
    return _memory
