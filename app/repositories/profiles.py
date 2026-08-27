"""Profile persistence contract with Memory and Postgres implementations."""

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
NULLABLE_PROFILE_FIELDS = (
    "areaCode",
    "prefectureCode",
    "birthYear",
    "notes",
    "helperType",
    "university",
    "faculty",
    "schoolYear",
    "occupation",
    "industry",
    "workplace",
    "interest",
    "message",
    "updatedAt",
)


class ProfileValidationError(ValueError):
    """The resulting complete profile violates a cross-field rule."""


class ProfileRepository(Protocol):
    async def get(self, actor: CurrentUser) -> ProfileRecord | None: ...

    async def update(
        self, actor: CurrentUser, changes: dict[str, Any]
    ) -> ProfileRecord: ...

    async def list_areas(self) -> list[dict[str, str]]: ...


def _iso(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return value.isoformat().replace("+00:00", "Z")


def _row_to_profile(row: Any) -> ProfileRecord:
    return {
        "id": row["auth_subject"],
        "displayName": row["display_name"],
        "role": row["role"],
        "emailVerified": row["email_verified"],
        "verificationStatus": row["verification_status"],
        "areaCode": row["area_code"],
        "prefectureCode": row["prefecture_code"],
        "birthYear": row["birth_year"],
        "notes": row["notes"],
        "helperType": row["helper_type"],
        "university": row["university"],
        "faculty": row["faculty"],
        "schoolYear": row["school_year"],
        "occupation": row["occupation"],
        "industry": row["industry"],
        "workplace": row["workplace"],
        "interest": row["interest"],
        "message": row["message"],
        "status": row["status"],
        "updatedAt": _iso(row["updated_at"]),
    }


def _normalise_changes(changes: dict[str, Any]) -> dict[str, Any]:
    normalised = dict(changes)
    for key, value in normalised.items():
        if isinstance(value, str):
            normalised[key] = value.strip()
    return normalised


def _complete_memory_profile(item: ProfileRecord) -> ProfileRecord:
    profile = deepcopy(item)
    for key in NULLABLE_PROFILE_FIELDS:
        profile.setdefault(key, None)
    return profile


def _merged_profile(
    current: ProfileRecord, changes: dict[str, Any]
) -> ProfileRecord:
    merged = {**current, **_normalise_changes(changes)}
    if not merged.get("displayName"):
        raise ProfileValidationError("displayName cannot be blank")
    for key in ("university", "faculty", "occupation"):
        if key in changes and merged.get(key) == "":
            raise ProfileValidationError(f"{key} cannot be blank")
    if "helperType" in changes:
        if merged["helperType"] == "student":
            for key in ("occupation", "industry", "workplace"):
                merged[key] = None
        elif merged["helperType"] == "worker":
            for key in ("university", "faculty", "schoolYear"):
                merged[key] = None
        else:
            for key in (
                "university",
                "faculty",
                "schoolYear",
                "occupation",
                "industry",
                "workplace",
            ):
                merged[key] = None

    helper_type = merged.get("helperType")
    if helper_type == "student":
        if not all(
            merged.get(key) for key in ("university", "faculty", "schoolYear")
        ):
            raise ProfileValidationError("student helper details are required")
        if any(
            merged.get(key) is not None
            for key in ("occupation", "industry", "workplace")
        ):
            raise ProfileValidationError("worker details are not allowed for students")
    elif helper_type == "worker":
        if not merged.get("occupation"):
            raise ProfileValidationError("worker occupation is required")
        if any(
            merged.get(key) is not None
            for key in ("university", "faculty", "schoolYear")
        ):
            raise ProfileValidationError("student details are not allowed for workers")
    elif any(
        merged.get(key) is not None
        for key in (
            "university",
            "faculty",
            "schoolYear",
            "occupation",
            "industry",
            "workplace",
        )
    ):
        raise ProfileValidationError("helperType is required for helper details")
    return merged


class MemoryProfileRepository:
    def __init__(self, store_provider: StoreProvider) -> None:
        self._store_provider = store_provider

    async def get(self, actor: CurrentUser) -> ProfileRecord | None:
        item = self._store_provider().get(actor.user_id)
        return _complete_memory_profile(item) if item is not None else None

    async def update(
        self, actor: CurrentUser, changes: dict[str, Any]
    ) -> ProfileRecord:
        from app.cruds import main as runtime

        store = self._store_provider()
        current = store.get(actor.user_id)
        if current is None:
            raise KeyError(actor.user_id)
        if (
            changes.get("areaCode") is not None
            and changes["areaCode"] not in runtime.REGIONS
        ):
            raise ProfileValidationError("unknown areaCode")
        merged = _merged_profile(_complete_memory_profile(current), changes)
        merged["updatedAt"] = datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
        store[actor.user_id] = merged
        return deepcopy(merged)

    async def list_areas(self) -> list[dict[str, str]]:
        from app.cruds import main as runtime

        return [
            {
                "code": code,
                "label": values["label"],
                "prefectureCode": values.get("prefectureCode", "01"),
            }
            for code, values in runtime.REGIONS.items()
        ]


class PostgresProfileRepository:
    async def get(self, actor: CurrentUser) -> ProfileRecord | None:
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(
                """
                select auth_subject, display_name, role, email_verified,
                       verification_status, area_code, prefecture_code, birth_year,
                       notes, helper_type, university, faculty, school_year,
                       occupation, industry, workplace, interest, message, status,
                       updated_at
                  from users
                 where id = app.current_actor()
                """
            )
        return _row_to_profile(row) if row is not None else None

    async def update(
        self, actor: CurrentUser, changes: dict[str, Any]
    ) -> ProfileRecord:
        async with actor_connection(actor) as conn:
            current_row = await conn.fetchrow(
                """
                select auth_subject, display_name, role, email_verified,
                       verification_status, area_code, prefecture_code, birth_year,
                       notes, helper_type, university, faculty, school_year,
                       occupation, industry, workplace, interest, message, status,
                       updated_at
                  from users
                 where id = app.current_actor()
                """
            )
            if current_row is None:
                raise KeyError(actor.user_id)
            current = _row_to_profile(current_row)
            merged = _merged_profile(current, changes)
            patch = {key: merged[key] for key in changes}
            if "helperType" in changes:
                patch.update(
                    {
                        key: merged[key]
                        for key in (
                            "university",
                            "faculty",
                            "schoolYear",
                            "occupation",
                            "industry",
                            "workplace",
                        )
                    }
                )
            try:
                row = await conn.fetchrow(
                    "select * from app.update_own_profile($1::jsonb)",
                    json.dumps(patch),
                )
            except (
                asyncpg.CheckViolationError,
                asyncpg.ForeignKeyViolationError,
            ) as exc:
                raise ProfileValidationError("profile violates a database constraint") from exc
        if row is None:
            raise KeyError(actor.user_id)
        return _row_to_profile(row)

    async def list_areas(self) -> list[dict[str, str]]:
        async with admin_connection() as conn:
            rows = await conn.fetch(
                """
                select code, label, prefecture_code
                  from app.list_active_operational_areas()
                 order by sort_order, code
                """
            )
        return [
            {
                "code": row["code"],
                "label": row["label"],
                "prefectureCode": row["prefecture_code"],
            }
            for row in rows
        ]


async def resolve_authenticated_user(auth_subject: str) -> ProfileRecord | None:
    """Resolve or lazily provision a SuperTokens subject without Memory state."""

    async with admin_connection() as conn:
        row = await conn.fetchrow(
            "select * from app.resolve_authenticated_user($1)", auth_subject
        )
    return _row_to_profile(row) if row is not None else None


_memory_repository: MemoryProfileRepository | None = None
_postgres_repository = PostgresProfileRepository()


def configure_memory_profile_store(store_provider: StoreProvider) -> None:
    global _memory_repository
    _memory_repository = MemoryProfileRepository(store_provider)


def get_profile_repository() -> ProfileRepository:
    if settings.request_repository == "postgres":
        return _postgres_repository
    if _memory_repository is None:
        raise RuntimeError("Memory profile store is not configured")
    return _memory_repository
