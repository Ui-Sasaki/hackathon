"""Verification-request persistence; document storage stays behind UploadRepository."""

from __future__ import annotations

import json
from typing import Any, Protocol

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings

VerificationRecord = dict[str, Any]


class VerificationRepositoryError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class VerificationRepository(Protocol):
    async def has_pending(self, actor: CurrentUser) -> bool: ...

    async def create(
        self, actor: CurrentUser, *, method: str, storage_object_key: str | None,
        image_id: str | None = None,
    ) -> VerificationRecord: ...


class MemoryVerificationRepository:
    async def has_pending(self, actor: CurrentUser) -> bool:
        from app.cruds import main as runtime
        return any(item["status"] == "pending" and item["userId"] == actor.user_id
                   for item in runtime.verifications.values())

    async def create(
        self, actor: CurrentUser, *, method: str, storage_object_key: str | None,
        image_id: str | None = None,
    ) -> VerificationRecord:
        from app.cruds import main as runtime

        if any(item["status"] == "pending" and item["userId"] == actor.user_id
               for item in runtime.verifications.values()):
            raise VerificationRepositoryError("VERIFICATION_ALREADY_PENDING")
        item = {
            "id": runtime.new_id("verification"), "userId": actor.user_id,
            "method": method, "_imageId": image_id,
            "_storageObjectKey": storage_object_key, "status": "pending",
            "createdAt": runtime.now_iso(),
        }
        runtime.verifications[item["id"]] = item
        runtime.users_store[actor.user_id]["verificationStatus"] = "pending"
        runtime.record_audit_event(
            actor_id=actor.user_id, event_type="verification_requested",
            target_type="verification_request", target_id=item["id"],
        )
        return item


class PostgresVerificationRepository:
    async def has_pending(self, actor: CurrentUser) -> bool:
        async with actor_connection(actor) as conn:
            return bool(await conn.fetchval(
                "select exists (select 1 from verification_requests "
                "where user_id = app.current_actor() and status = 'pending')"
            ))

    async def create(
        self, actor: CurrentUser, *, method: str, storage_object_key: str | None,
        image_id: str | None = None,
    ) -> VerificationRecord:
        del image_id
        async with actor_connection(actor) as conn:
            raw = await conn.fetchval(
                "select app.create_verification_request($1, $2)", method, storage_object_key
            )
        result = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if result.get("code") != "CREATED":
            raise VerificationRepositoryError(str(result.get("code", "BAD_REQUEST")))
        return {
            "id": result["id"], "userId": result["userId"],
            "method": result["method"], "status": result["status"],
            "createdAt": result["createdAt"],
        }


_memory = MemoryVerificationRepository()
_postgres = PostgresVerificationRepository()


async def get_verification_repository() -> VerificationRepository:
    return _postgres if settings.request_repository == "postgres" else _memory
