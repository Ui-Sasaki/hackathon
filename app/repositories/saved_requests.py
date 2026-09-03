"""Persistence boundary for requests saved by a user."""

from __future__ import annotations

from typing import Protocol

from app.auth import CurrentUser


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


saved_request_repository: SavedRequestRepository = MemorySavedRequestRepository()


def get_saved_request_repository() -> SavedRequestRepository:
    return saved_request_repository
