"""Storage-independent request authorization and transition rules."""

from fastapi import HTTPException

from app.auth import CurrentUser
from app.repositories.requests import RequestRecord, RequestRepository


async def require_request(
    repository: RequestRepository, actor: CurrentUser, request_id: str
) -> RequestRecord:
    item = await repository.get(actor, request_id)
    if item is None:
        raise HTTPException(404, detail={"code": "REQUEST_NOT_FOUND"})
    return item


async def update_owned_request(
    repository: RequestRepository, actor: CurrentUser, request_id: str,
    expected_version: int, changes: dict,
) -> RequestRecord:
    item = await require_request(repository, actor, request_id)
    if item["requesterId"] != actor.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if item["status"] not in {"draft", "pending_review", "published"}:
        raise HTTPException(409, detail={"code": "REQUEST_NOT_EDITABLE"})
    if item["version"] != expected_version:
        raise HTTPException(409, detail={
            "code": "REQUEST_STATE_CONFLICT", "currentVersion": item["version"],
        })
    if changes.get("requiredHelpers", item["requiredHelpers"]) < item["acceptedHelpers"]:
        raise HTTPException(409, detail={"code": "HELPER_COUNT_CONFLICT"})
    if not changes:
        return item
    updated = await repository.update(actor, request_id, expected_version, changes)
    if updated is None:
        raise HTTPException(409, detail={
            "code": "REQUEST_STATE_CONFLICT", "currentVersion": item["version"],
        })
    return updated


async def cancel_owned_request(
    repository: RequestRepository, actor: CurrentUser, request_id: str
) -> None:
    item = await require_request(repository, actor, request_id)
    if item["requesterId"] != actor.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if item["status"] in {"completed", "cancelled"}:
        raise HTTPException(409, detail={"code": "INVALID_REQUEST_TRANSITION"})
    if not await repository.cancel(actor, request_id, item["version"]):
        raise HTTPException(409, detail={"code": "REQUEST_STATE_CONFLICT"})
