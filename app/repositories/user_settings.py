"""Persistence boundary for per-user application settings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from typing import Literal, Protocol, TypedDict

from app.auth import CurrentUser
from app.db import actor_connection, admin_connection
from app.settings import settings


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
    """Process-local implementation for tests and local development."""

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


def _row_to_record(row: Any) -> UserSettingsRecord:
    return {
        "notificationsEnabled": row["notifications_enabled"],
        "locationEnabled": row["location_enabled"],
        "fontSize": row["font_size"],
    }


class PostgresUserSettingsRepository:
    async def get(self, actor: CurrentUser) -> UserSettingsRecord:
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(
                """insert into user_settings (user_id)
                   values (app.current_actor())
                   on conflict (user_id) do update
                     set updated_at = user_settings.updated_at
                   returning notifications_enabled, location_enabled, font_size"""
            )
        return _row_to_record(row)

    async def update(
        self, actor: CurrentUser, changes: dict[str, bool | FontSize]
    ) -> UserSettingsRecord:
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(
                """insert into user_settings (
                       user_id, notifications_enabled, location_enabled, font_size
                   ) values (
                       app.current_actor(),
                       coalesce($1::boolean, true),
                       coalesce($2::boolean, true),
                       coalesce($3::text, 'medium')
                   )
                   on conflict (user_id) do update set
                     notifications_enabled = coalesce($1::boolean,
                                                      user_settings.notifications_enabled),
                     location_enabled = coalesce($2::boolean,
                                                 user_settings.location_enabled),
                     font_size = coalesce($3::text, user_settings.font_size),
                     updated_at = now()
                   returning notifications_enabled, location_enabled, font_size""",
                changes.get("notificationsEnabled"),
                changes.get("locationEnabled"),
                changes.get("fontSize"),
            )
        return _row_to_record(row)

    async def reset(self) -> None:
        async with admin_connection() as conn:
            await conn.execute("delete from user_settings")


_memory = MemoryUserSettingsRepository()
_postgres = PostgresUserSettingsRepository()


def get_user_settings_repository() -> UserSettingsRepository:
    return _postgres if settings.request_repository == "postgres" else _memory
