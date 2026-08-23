"""Storage-independent application authorization and transition rules."""

from datetime import datetime, timezone

from fastapi import HTTPException

from app.auth import CurrentUser
from app.repositories.applications import (
    ApplicationEligibilityError, ApplicationRecord, ApplicationRepository,
    DuplicateApplicationError,
)
from app.repositories.requests import RequestRecord


def _is_expired(request_item: RequestRecord) -> bool:
    expires_at = request_item.get("expiresAt")
    if expires_at is None:
        return False
    return datetime.fromisoformat(expires_at.replace("Z", "+00:00")) <= datetime.now(timezone.utc)


async def create_application(
    repository: ApplicationRepository,
    actor: CurrentUser,
    request_item: RequestRecord,
    values: dict,
) -> ApplicationRecord:
    if request_item["requesterId"] == actor.user_id:
        raise HTTPException(403, detail={"code": "SELF_APPLICATION_NOT_ALLOWED"})
    if request_item["status"] != "published":
        raise HTTPException(409, detail={"code": "REQUEST_NOT_OPEN"})
    if _is_expired(request_item):
        raise HTTPException(409, detail={"code": "REQUEST_EXPIRED"})
    if request_item.get("verificationRequired") and actor.verification_status != "approved":
        raise HTTPException(403, detail={"code": "VERIFICATION_REQUIRED"})
    try:
        return await repository.create(actor, request_item["id"], values)
    except DuplicateApplicationError as exc:
        raise HTTPException(409, detail={"code": "DUPLICATE_APPLICATION"}) from exc
    except ApplicationEligibilityError as exc:
        # State, deadline, verification, or block status changed after the API check.
        raise HTTPException(409, detail={"code": "REQUEST_STATE_CONFLICT"}) from exc


async def withdraw_application(
    repository: ApplicationRepository, actor: CurrentUser, application_id: str
) -> ApplicationRecord:
    item = await repository.get(actor, application_id)
    if item is None:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    if item["helperId"] != actor.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if item["status"] != "applied":
        raise HTTPException(409, detail={"code": "APPLICATION_NOT_WITHDRAWABLE"})
    if not await repository.withdraw(actor, application_id):
        raise HTTPException(409, detail={"code": "APPLICATION_NOT_WITHDRAWABLE"})
    updated = await repository.get(actor, application_id)
    if updated is None:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    return updated
