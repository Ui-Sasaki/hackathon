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


async def publish_owned_request(
    repository: RequestRepository, actor: CurrentUser, request_id: str
) -> RequestRecord:
    """依頼者本人が draft の依頼を published へ進める。

    作成APIは危険度判定を通した依頼を draft で保存するだけなので、支援者の
    一覧に載せるにはこの遷移が必要になる。審査待ち（pending_review）は管理者の
    判断を待つため本人からは公開できない。
    """
    item = await require_request(repository, actor, request_id)
    if item["requesterId"] != actor.user_id:
        raise HTTPException(403, detail={"code": "ROLE_FORBIDDEN"})
    if item["status"] == "pending_review":
        raise HTTPException(409, detail={"code": "REQUEST_UNDER_REVIEW"})
    if item["status"] != "draft":
        raise HTTPException(409, detail={"code": "INVALID_REQUEST_TRANSITION"})
    if not await repository.set_status(
        actor, request_id, "published", expected_version=item["version"],
    ):
        raise HTTPException(409, detail={"code": "REQUEST_STATE_CONFLICT"})
    return await require_request(repository, actor, request_id)


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
