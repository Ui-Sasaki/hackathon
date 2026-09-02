"""Persistence boundary for per-user application settings."""

from __future__ import annotations

from copy import deepcopy
from typing import Literal, Protocol, TypedDict

from app.auth import CurrentUser


FontSize = Literal["small", "medium", "large"]


class UserSettingsRecord(TypedDict):
    notificationsEnabled: bool
    locationEnabled: bool
    fontSize: FontSize


DEFAULT_USER_SETTINGS: UserSettingsRecord = {
    "notificationsEnabled": True,
    "locationEnabled": True,
    "fontSize": "medium",
}


class UserSettingsRepository(Protocol):
    async def get(self, actor: CurrentUser) -> UserSettingsRecord: ...

    async def update(
        self, actor: CurrentUser, changes: dict[str, bool | FontSize]
    ) -> UserSettingsRecord: ...

    async def reset(self) -> None: ...


class MemoryUserSettingsRepository:
    """Process-local implementation; Postgres wiring belongs to the DB owner."""

    def __init__(self) -> None:
        self._items: dict[str, UserSettingsRecord] = {}

    async def get(self, actor: CurrentUser) -> UserSettingsRecord:
        item = self._items.setdefault(actor.user_id, deepcopy(DEFAULT_USER_SETTINGS))
        return deepcopy(item)

    async def update(
        self, actor: CurrentUser, changes: dict[str, bool | FontSize]
    ) -> UserSettingsRecord:
        item = self._items.setdefault(actor.user_id, deepcopy(DEFAULT_USER_SETTINGS))
        item.update(changes)  # type: ignore[typeddict-item]
        return deepcopy(item)

    async def reset(self) -> None:
        self._items.clear()


user_settings_repository: UserSettingsRepository = MemoryUserSettingsRepository()


def get_user_settings_repository() -> UserSettingsRepository:
    return user_settings_repository
