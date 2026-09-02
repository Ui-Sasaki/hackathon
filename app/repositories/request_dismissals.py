"""Persistence boundary for per-user dismissed requests."""

from __future__ import annotations

from typing import Protocol

from app.auth import CurrentUser


class RequestDismissalRepository(Protocol):
    async def list_ids(self, actor: CurrentUser) -> set[str]: ...

    async def dismiss(self, actor: CurrentUser, request_id: str) -> None: ...

    async def restore(self, actor: CurrentUser, request_id: str) -> None: ...

    async def reset(self) -> None: ...


class MemoryRequestDismissalRepository:
    def __init__(self) -> None:
        self._relations: set[tuple[str, str]] = set()

    async def list_ids(self, actor: CurrentUser) -> set[str]:
        return {
            request_id
            for user_id, request_id in self._relations
            if user_id == actor.user_id
        }

    async def dismiss(self, actor: CurrentUser, request_id: str) -> None:
        self._relations.add((actor.user_id, request_id))

    async def restore(self, actor: CurrentUser, request_id: str) -> None:
        self._relations.discard((actor.user_id, request_id))

    async def reset(self) -> None:
        self._relations.clear()


request_dismissal_repository: RequestDismissalRepository = (
    MemoryRequestDismissalRepository()
)


def get_request_dismissal_repository() -> RequestDismissalRepository:
    return request_dismissal_repository
