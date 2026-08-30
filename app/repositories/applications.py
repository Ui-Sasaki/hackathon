"""Application persistence interface plus Memory and Postgres implementations."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Protocol
import uuid

import asyncpg

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings


ApplicationRecord = dict[str, Any]


class DuplicateApplicationError(Exception):
    """The actor already has an application for the request."""


def _iso(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return value.isoformat().replace("+00:00", "Z")


def _row_to_record(row: Any) -> ApplicationRecord:
    record = {
        "id": str(row["id"]),
        "requestId": str(row["request_id"]),
        "helperId": row["helper_auth_subject"],
        "message": row["message"],
        "availableAt": _iso(row["available_at"]),
        "status": row["status"],
        "createdAt": _iso(row["created_at"]),
        "updatedAt": _iso(row["updated_at"]),
    }
    if "helper_display_name" in row:
        record["helper"] = {
            "id": row["helper_auth_subject"],
            "displayName": row["helper_display_name"],
            "verificationStatus": row["helper_verification_status"],
            "universityVerified": row["helper_email_verified"],
            "skillTags": [],
            "achievementCount": row["achievement_count"],
        }
    return record


class ApplicationRepository(Protocol):
    async def list_for_request(
        self, actor: CurrentUser, request_id: str
    ) -> list[ApplicationRecord]: ...

    async def get(
        self, actor: CurrentUser, application_id: str
    ) -> ApplicationRecord | None: ...

    async def create(
        self, actor: CurrentUser, request_id: str, values: dict[str, Any]
    ) -> ApplicationRecord: ...

    async def withdraw(self, actor: CurrentUser, application_id: str) -> bool: ...

    async def cancel_pending_for_request(
        self, actor: CurrentUser, request_id: str
    ) -> None: ...

    async def reset(self) -> None: ...


class MemoryApplicationRepository:
    def __init__(self) -> None:
        self._items: dict[str, ApplicationRecord] = {}
        self.reset_sync()

    def reset_sync(self) -> None:
        self._items = {
            "app_55": self._seed("app_55", "usr_207", "犬の散歩経験があります"),
            "app_56": self._seed("app_56", "usr_208", "丁寧に対応します"),
        }

    @staticmethod
    def _seed(application_id: str, helper_id: str, message: str) -> ApplicationRecord:
        return {
            "id": application_id,
            "requestId": "5fcfec7f-a8b0-58d4-931e-593d60355ee3",
            "helperId": helper_id,
            "message": message,
            "availableAt": "2026-08-19T17:00:00+09:00",
            "status": "applied",
            "createdAt": "2026-08-18T12:00:00+09:00",
            "updatedAt": None,
        }

    async def list_for_request(
        self, actor: CurrentUser, request_id: str
    ) -> list[ApplicationRecord]:
        del actor
        items = [item for item in self._items.values() if item["requestId"] == request_id]
        items.sort(key=lambda item: (item["createdAt"], item["id"]))
        return deepcopy(items)

    async def get(
        self, actor: CurrentUser, application_id: str
    ) -> ApplicationRecord | None:
        del actor
        item = self._items.get(application_id)
        return deepcopy(item) if item else None

    async def create(
        self, actor: CurrentUser, request_id: str, values: dict[str, Any]
    ) -> ApplicationRecord:
        if any(
            item["requestId"] == request_id and item["helperId"] == actor.user_id
            for item in self._items.values()
        ):
            raise DuplicateApplicationError
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        item = {
            "id": str(uuid.uuid4()),
            "requestId": request_id,
            "helperId": actor.user_id,
            **deepcopy(values),
            "status": "applied",
            "createdAt": now,
            "updatedAt": None,
        }
        self._items[item["id"]] = item
        return deepcopy(item)

    async def withdraw(self, actor: CurrentUser, application_id: str) -> bool:
        item = self._items.get(application_id)
        if item is None or item["helperId"] != actor.user_id or item["status"] != "applied":
            return False
        item["status"] = "withdrawn"
        item["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return True

    async def cancel_pending_for_request(
        self, actor: CurrentUser, request_id: str
    ) -> None:
        del actor
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for item in self._items.values():
            if item["requestId"] == request_id and item["status"] == "applied":
                item["status"] = "cancelled"
                item["updatedAt"] = now

    async def reset(self) -> None:
        self.reset_sync()


class PostgresApplicationRepository:
    _SELECT = """
        select a.id, a.request_id, a.message, a.available_at, a.status,
               a.created_at, a.updated_at,
               app.auth_subject_of(a.helper_id) as helper_auth_subject
          from applications a
    """

    async def list_for_request(
        self, actor: CurrentUser, request_id: str
    ) -> list[ApplicationRecord]:
        try:
            parsed_id = uuid.UUID(request_id)
        except ValueError:
            return []
        async with actor_connection(actor) as conn:
            rows = await conn.fetch(
                """select a.id, a.request_id, a.message, a.available_at, a.status,
                          a.created_at, a.updated_at,
                          app.auth_subject_of(a.helper_id) as helper_auth_subject,
                          helper_profile.data ->> 'display_name' as helper_display_name,
                          helper_profile.data ->> 'verification_status' as helper_verification_status,
                          (helper_profile.data ->> 'email_verified')::boolean as helper_email_verified,
                          (helper_profile.data ->> 'achievement_count')::integer as achievement_count
                     from applications a
                     cross join lateral (
                         select app.application_helper_profile_for_application(a.id) as data
                     ) helper_profile
                    where a.request_id = $1
                    order by a.created_at, a.id""",
                parsed_id,
            )
        return [_row_to_record(row) for row in rows]

    async def get(
        self, actor: CurrentUser, application_id: str
    ) -> ApplicationRecord | None:
        try:
            parsed_id = uuid.UUID(application_id)
        except ValueError:
            return None
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(self._SELECT + " where a.id = $1", parsed_id)
        return _row_to_record(row) if row else None

    async def create(
        self, actor: CurrentUser, request_id: str, values: dict[str, Any]
    ) -> ApplicationRecord:
        try:
            async with actor_connection(actor) as conn:
                row = await conn.fetchrow(
                    """insert into applications (
                           request_id, helper_id, message, available_at
                       ) values ($1, app.current_actor(), $2, $3)
                       returning id, request_id, message, available_at, status,
                                 created_at, updated_at""",
                    uuid.UUID(request_id), values["message"],
                    datetime.fromisoformat(values["availableAt"]),
                )
        except asyncpg.UniqueViolationError as exc:
            raise DuplicateApplicationError from exc
        return _row_to_record({**dict(row), "helper_auth_subject": actor.user_id})

    async def withdraw(self, actor: CurrentUser, application_id: str) -> bool:
        try:
            parsed_id = uuid.UUID(application_id)
        except ValueError:
            return False
        async with actor_connection(actor) as conn:
            updated = await conn.fetchval("select app.withdraw_application($1)", parsed_id)
        return updated is not None

    async def cancel_pending_for_request(
        self, actor: CurrentUser, request_id: str
    ) -> None:
        # app.cancel_request() performs this atomically with request cancellation.
        del actor, request_id

    async def reset(self) -> None:
        # Applications are removed by app.mock_reset_requests() through the request FK.
        return None


application_repository: ApplicationRepository = (
    PostgresApplicationRepository()
    if settings.request_repository == "postgres"
    else MemoryApplicationRepository()
)


def get_application_repository() -> ApplicationRepository:
    return application_repository
