"""Persistence boundary for requests saved by a user."""

from __future__ import annotations

from typing import Protocol
import uuid

from app.auth import CurrentUser
from app.db import actor_connection, admin_connection
from app.settings import settings


class SavedRequestRepository(Protocol):
    async def list_ids(self, actor: CurrentUser) -> set[str]: ...

    async def save(self, actor: CurrentUser, request_id: str) -> None: ...

    async def remove(self, actor: CurrentUser, request_id: str) -> None: ...

    async def reset(self) -> None: ...


class MemorySavedRequestRepository:
    def __init__(self) -> None:
        self._relations: set[tuple[str, str]] = set()

    async def list_ids(self, actor: CurrentUser) -> set[str]:
        return {
            request_id
            for user_id, request_id in self._relations
            if user_id == actor.user_id
        }

    async def save(self, actor: CurrentUser, request_id: str) -> None:
        self._relations.add((actor.user_id, request_id))

    async def remove(self, actor: CurrentUser, request_id: str) -> None:
        self._relations.discard((actor.user_id, request_id))

    async def reset(self) -> None:
        self._relations.clear()


class PostgresSavedRequestRepository:
    async def list_ids(self, actor: CurrentUser) -> set[str]:
        async with actor_connection(actor) as conn:
            rows = await conn.fetch(
                "select request_id from saved_requests where user_id = app.current_actor()"
            )
        return {str(row["request_id"]) for row in rows}

    async def save(self, actor: CurrentUser, request_id: str) -> None:
        async with actor_connection(actor) as conn:
            await conn.execute(
                """insert into saved_requests (user_id, request_id)
                   values (app.current_actor(), $1)
                   on conflict do nothing""",
                uuid.UUID(request_id),
            )

    async def remove(self, actor: CurrentUser, request_id: str) -> None:
        async with actor_connection(actor) as conn:
            await conn.execute(
                "delete from saved_requests where user_id = app.current_actor() and request_id = $1",
                uuid.UUID(request_id),
            )

    async def reset(self) -> None:
        async with admin_connection() as conn:
            await conn.execute("delete from saved_requests")


_memory = MemorySavedRequestRepository()
_postgres = PostgresSavedRequestRepository()


def get_saved_request_repository() -> SavedRequestRepository:
    return _postgres if settings.request_repository == "postgres" else _memory
