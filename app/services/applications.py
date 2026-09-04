"""Storage-independent application authorization and transition rules."""

from datetime import datetime, timezone

from fastapi import HTTPException

from app.auth import CurrentUser
from app.repositories.applications import (
    ApplicationRecord, ApplicationRepository, DuplicateApplicationError,
)
from app.repositories.requests import RequestRecord, RequestRepository


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


async def select_application(
    application_repository: ApplicationRepository,
    request_repository: RequestRepository,
    actor: CurrentUser,
    application_id: str,
    expected_version: int,
    *,
    blocked: bool,
    helper_verified: bool,
) -> tuple[ApplicationRecord, RequestRecord, dict | None]:
    item = await application_repository.get(actor, application_id)
    if item is None or blocked:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    request_item = await request_repository.get(actor, item["requestId"])
    if request_item is None:
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    if request_item["requesterId"] != actor.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if request_item["version"] != expected_version:
        raise HTTPException(409, detail={
            "code": "REQUEST_STATE_CONFLICT",
            "currentVersion": request_item["version"],
        })
    if item["status"] != "applied":
        raise HTTPException(409, detail={"code": "APPLICATION_NOT_SELECTABLE"})
    if request_item.get("verificationRequired") and not helper_verified:
        raise HTTPException(409, detail={"code": "HELPER_VERIFICATION_REQUIRED"})
    if request_item["acceptedHelpers"] >= request_item["requiredHelpers"]:
        raise HTTPException(409, detail={"code": "CAPACITY_REACHED"})

    select_atomically = getattr(application_repository, "select_atomically", None)
    if callable(select_atomically):
        result = await select_atomically(actor, application_id, expected_version)
        code = result.get("code")
        if code != "SELECTED":
            status_code = (
                403 if code == "ROLE_FORBIDDEN"
                else 404 if code == "APPLICATION_NOT_FOUND"
                else 409
            )
            detail = {"code": code or "REQUEST_STATE_CONFLICT"}
            if result.get("currentVersion") is not None:
                detail["currentVersion"] = result["currentVersion"]
            raise HTTPException(status_code, detail=detail)
        updated_application = await application_repository.get(actor, application_id)
        updated_request = await request_repository.get(actor, item["requestId"])
        if updated_application is None or updated_request is None:
            raise HTTPException(500, detail={"code": "SELECTION_RESULT_UNAVAILABLE"})
        return updated_application, updated_request, result

    reserve_helper = getattr(request_repository, "reserve_helper", None)
    select = getattr(application_repository, "select", None)
    if not callable(reserve_helper) or not callable(select):
        raise HTTPException(503, detail={"code": "APPLICATION_SELECTION_UNAVAILABLE"})

    updated_request = await reserve_helper(actor, item["requestId"], expected_version)
    if updated_request is None:
        raise HTTPException(409, detail={"code": "REQUEST_STATE_CONFLICT"})
    selected = await select(
        actor,
        application_id,
        close_remaining=updated_request["status"] == "matched",
    )
    if not selected:
        raise HTTPException(409, detail={"code": "APPLICATION_NOT_SELECTABLE"})
    updated_application = await application_repository.get(actor, application_id)
    if updated_application is None:
        raise HTTPException(404, detail={"code": "APPLICATION_NOT_FOUND"})
    return updated_application, updated_request, None
