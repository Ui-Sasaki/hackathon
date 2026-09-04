"""User block persistence contract with Memory and Postgres implementations."""

from __future__ import annotations

import json
from typing import Any, Protocol

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings


BlockRecord = dict[str, Any]


class BlockRepositoryError(Exception):
    """The requested block operation is not allowed."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BlockRepository(Protocol):
    async def set(
        self, actor: CurrentUser, target_user_id: str, blocked: bool
    ) -> BlockRecord: ...


class MemoryBlockRepository:
    async def set(
        self, actor: CurrentUser, target_user_id: str, blocked: bool
    ) -> BlockRecord:
        from app.cruds import main as runtime

        if target_user_id == actor.user_id:
            raise BlockRepositoryError("SELF_BLOCK_NOT_ALLOWED")
        if target_user_id not in runtime.users_store:
            raise BlockRepositoryError("USER_PROFILE_NOT_FOUND")
        relation = (actor.user_id, target_user_id)
        if blocked:
            runtime.blocks.add(relation)
        else:
            runtime.blocks.discard(relation)
        runtime.record_audit_event(
            actor_id=actor.user_id,
            event_type="user_blocked" if blocked else "user_unblocked",
            target_type="user",
            target_id=target_user_id,
        )
        return {
            "userId": target_user_id,
            "blocked": relation in runtime.blocks,
            "updatedAt": runtime.now_iso(),
        }


class PostgresBlockRepository:
    async def set(
        self, actor: CurrentUser, target_user_id: str, blocked: bool
    ) -> BlockRecord:
        async with actor_connection(actor) as conn:
            raw = await conn.fetchval(
                "select app.set_own_block($1, $2)", target_user_id, blocked
            )
        result = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if result.get("code") != "OK":
            raise BlockRepositoryError(str(result.get("code", "BAD_REQUEST")))
        return {
            "userId": result["userId"],
            "blocked": result["blocked"],
            "updatedAt": result["updatedAt"],
        }


_memory = MemoryBlockRepository()
_postgres = PostgresBlockRepository()


async def get_block_repository() -> BlockRepository:
    # Keep this dependency on the request event loop. The legacy synchronous
    # ASGI test client creates a fresh loop per call and can deadlock while
    # dispatching a new sync dependency through AnyIO's worker portal.
    return _postgres if settings.request_repository == "postgres" else _memory
