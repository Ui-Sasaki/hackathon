"""Authenticated user resolution and profile persistence."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any, Protocol

import asyncpg

from app.auth import CurrentUser
from app.db import actor_connection, admin_connection
from app.settings import settings

ProfileRecord = dict[str, Any]
StoreProvider = Callable[[], dict[str, ProfileRecord]]
PROFILE_FIELDS = (
    "region", "age", "notes", "helperType", "university", "faculty",
    "schoolYear", "occupation", "industry", "workplace", "gender",
    "interest", "message", "updatedAt",
)


class ProfileValidationError(ValueError):
    def __init__(self, message: str, code: str = "PROFILE_VALIDATION_ERROR") -> None:
        self.code = code
        super().__init__(message)


class ProfileRepository(Protocol):
    async def get(self, actor: CurrentUser) -> ProfileRecord | None: ...
    async def update(self, actor: CurrentUser, changes: dict[str, Any]) -> ProfileRecord: ...


def _complete(item: ProfileRecord) -> ProfileRecord:
    result = deepcopy(item)
    for key in PROFILE_FIELDS:
        result.setdefault(key, None)
    return result


def _validate(current: ProfileRecord, changes: dict[str, Any]) -> ProfileRecord:
    cleaned = {
        key: value.strip() if isinstance(value, str) else value
        for key, value in changes.items()
    }
    merged = {**_complete(current), **cleaned}
    if not merged.get("displayName"):
        raise ProfileValidationError("displayName cannot be blank")
    if "helperType" in changes:
        if merged["helperType"] == "student":
            for key in ("occupation", "industry", "workplace"):
                merged[key] = None
        elif merged["helperType"] == "worker":
            for key in ("university", "faculty", "schoolYear"):
                merged[key] = None
        else:
            for key in ("university", "faculty", "schoolYear", "occupation", "industry", "workplace"):
                merged[key] = None
    if merged.get("helperType") == "student" and not all(
        merged.get(key) for key in ("university", "faculty", "schoolYear")
    ):
        raise ProfileValidationError(
            "student helper details are required", "STUDENT_PROFILE_INCOMPLETE"
        )
    if merged.get("helperType") == "worker" and not merged.get("occupation"):
        raise ProfileValidationError(
            "worker occupation is required", "WORKER_PROFILE_INCOMPLETE"
        )
    return merged


def _row(row: Any) -> ProfileRecord:
    def iso(value: Any) -> str | None:
        if value is None or isinstance(value, str):
            return value
        return value.isoformat().replace("+00:00", "Z")
    return {
        "id": row["auth_subject"], "displayName": row["display_name"],
        "role": row["role"], "emailVerified": row["email_verified"],
        "verificationStatus": row["verification_status"], "areaCode": row["area_code"],
        "region": row["region"], "age": row["age"], "notes": row["notes"],
        "helperType": row["helper_type"], "university": row["university"],
        "faculty": row["faculty"], "schoolYear": row["school_year"],
        "occupation": row["occupation"], "industry": row["industry"],
        "workplace": row["workplace"], "gender": row["gender"],
        "interest": row["interest"], "message": row["message"],
        "status": row["status"], "updatedAt": iso(row["updated_at"]),
    }


class MemoryProfileRepository:
    def __init__(self, store_provider: StoreProvider) -> None:
        self._store_provider = store_provider

    async def get(self, actor: CurrentUser) -> ProfileRecord | None:
        item = self._store_provider().get(actor.user_id)
        return _complete(item) if item is not None else None

    async def update(self, actor: CurrentUser, changes: dict[str, Any]) -> ProfileRecord:
        store = self._store_provider()
        current = store.get(actor.user_id)
        if current is None:
            raise KeyError(actor.user_id)
        from app.cruds import main as runtime
        if changes.get("areaCode") is not None and changes["areaCode"] not in runtime.REGIONS:
            raise ProfileValidationError("unknown areaCode")
        merged = _validate(current, changes)
        merged["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        store[actor.user_id] = merged
        return deepcopy(merged)


class PostgresProfileRepository:
    async def get(self, actor: CurrentUser) -> ProfileRecord | None:
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow("select * from app.own_profile()")
        return _row(row) if row else None

    async def update(self, actor: CurrentUser, changes: dict[str, Any]) -> ProfileRecord:
        async with actor_connection(actor) as conn:
            current_row = await conn.fetchrow("select * from app.own_profile()")
            if current_row is None:
                raise KeyError(actor.user_id)
            merged = _validate(_row(current_row), changes)
            patch = {key: merged[key] for key in changes}
            if "helperType" in changes:
                patch.update({key: merged[key] for key in ("university", "faculty", "schoolYear", "occupation", "industry", "workplace")})
            try:
                row = await conn.fetchrow("select * from app.update_own_profile($1::jsonb)", json.dumps(patch))
            except (asyncpg.CheckViolationError, asyncpg.ForeignKeyViolationError, asyncpg.InvalidTextRepresentationError) as exc:
                raise ProfileValidationError("profile violates a database constraint") from exc
        if row is None:
            raise KeyError(actor.user_id)
        return _row(row)


async def resolve_authenticated_user(auth_subject: str) -> ProfileRecord | None:
    async with admin_connection() as conn:
        row = await conn.fetchrow("select * from app.resolve_authenticated_user($1)", auth_subject)
    return _row(row) if row else None


_memory: MemoryProfileRepository | None = None
_postgres = PostgresProfileRepository()


def configure_memory_profile_store(store_provider: StoreProvider) -> None:
    global _memory
    _memory = MemoryProfileRepository(store_provider)


def get_profile_repository() -> ProfileRepository:
    if settings.request_repository == "postgres":
        return _postgres
    if _memory is None:
        raise RuntimeError("Memory profile store is not configured")
    return _memory
