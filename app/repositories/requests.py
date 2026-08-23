"""Request persistence interface plus Memory and Postgres implementations."""

from __future__ import annotations

import base64
import binascii
from copy import deepcopy
from datetime import datetime, timezone
from dataclasses import dataclass
import json
import re
from typing import Any, Protocol, Sequence
import uuid

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings


RequestRecord = dict[str, Any]


@dataclass(frozen=True)
class RequestCursor:
    created_at: datetime
    request_id: str


class InvalidCursor(ValueError):
    """The cursor is malformed or no longer points at a request."""


_CURSOR_TOKEN = re.compile(r"^[A-Za-z0-9_-]+$")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise InvalidCursor("cursor timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def encode_cursor(item: RequestRecord) -> str:
    payload = {
        "createdAt": _parse_timestamp(str(item["createdAt"])).isoformat(),
        "id": str(item["id"]),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(token: str) -> RequestCursor:
    if not token or not _CURSOR_TOKEN.fullmatch(token):
        raise InvalidCursor("invalid cursor token")
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = json.loads(
            base64.b64decode(padded, altchars=b"-_", validate=True).decode("utf-8")
        )
        if not isinstance(payload, dict) or set(payload) != {"createdAt", "id"}:
            raise InvalidCursor("invalid cursor fields")
        if not isinstance(payload["createdAt"], str) or not isinstance(payload["id"], str):
            raise InvalidCursor("invalid cursor values")
        return RequestCursor(_parse_timestamp(payload["createdAt"]), payload["id"])
    except InvalidCursor:
        raise
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise InvalidCursor("invalid cursor token") from exc


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat().replace("+00:00", "Z")


def _normalise_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _scheduled_datetime(item: RequestRecord) -> datetime | None:
    value = item.get("scheduledAt")
    if value is None:
        return None
    if isinstance(value, datetime):
        return _normalise_datetime(value)
    return _parse_timestamp(str(value))


def _matches_list_filters(
    item: RequestRecord,
    *,
    scheduled_from: datetime | None,
    scheduled_to: datetime | None,
    required_helpers: int | None,
    max_distance_km: float | None,
    verification_status: str | None,
    blocked_requester_ids: Sequence[str],
) -> bool:
    scheduled_at = _scheduled_datetime(item)
    if scheduled_from is not None and (
        scheduled_at is None or scheduled_at < _normalise_datetime(scheduled_from)
    ):
        return False
    if scheduled_to is not None and (
        scheduled_at is None or scheduled_at > _normalise_datetime(scheduled_to)
    ):
        return False
    if required_helpers is not None and item["requiredHelpers"] != required_helpers:
        return False
    if max_distance_km is not None and item["distanceKm"] > max_distance_km:
        return False
    if (
        verification_status is not None
        and item.get("_requesterVerificationStatus") != verification_status
    ):
        return False
    return item["requesterId"] not in blocked_requester_ids


def _public_record(item: RequestRecord) -> RequestRecord:
    result = deepcopy(item)
    result.pop("_requesterVerificationStatus", None)
    return result


def _row_to_record(row: Any) -> RequestRecord:
    return {
        "id": str(row["id"]),
        "requesterId": row["requester_auth_subject"],
        "title": row["title"],
        "description": row["original_text"],
        "category": row["category_id"],
        "riskLevel": row["risk_level"],
        "areaCode": row["area_code"],
        "areaLabel": "大学周辺・約1km",
        "distanceKm": 1.0,
        "acceptedHelpers": row["accepted_helpers"],
        "scheduledAt": _iso(row["scheduled_at"]),
        "estimatedMinutes": row["estimated_minutes"],
        "requiredHelpers": row["required_helpers"],
        "status": row["status"],
        "version": row["version"],
        "warnings": [],
        "createdAt": _iso(row["created_at"]),
        "updatedAt": _iso(row["updated_at"]),
    }


class RequestRepository(Protocol):
    async def list(
        self, actor: CurrentUser, *, category: str | None, area_code: str | None,
        limit: int, cursor: RequestCursor | None = None,
        scheduled_from: datetime | None = None, scheduled_to: datetime | None = None,
        required_helpers: int | None = None, max_distance_km: float | None = None,
        verification_status: str | None = None,
        blocked_requester_ids: Sequence[str] | None = None,
    ) -> list[RequestRecord]: ...

    async def get(self, actor: CurrentUser, request_id: str) -> RequestRecord | None: ...

    async def create(
        self, actor: CurrentUser, values: dict[str, Any]
    ) -> RequestRecord: ...

    async def update(
        self, actor: CurrentUser, request_id: str, expected_version: int,
        changes: dict[str, Any],
    ) -> RequestRecord | None: ...

    async def cancel(
        self, actor: CurrentUser, request_id: str, expected_version: int
    ) -> bool: ...

    async def set_status(
        self, actor: CurrentUser, request_id: str, status: str,
        *, expected_version: int | None = None, bump_version: bool = True,
    ) -> bool: ...

    async def reset(self) -> None: ...


class MemoryRequestRepository:
    def __init__(self) -> None:
        self._items: dict[str, RequestRecord] = {}
        self.reset_sync()

    def reset_sync(self) -> None:
        self._items = {
            "5fcfec7f-a8b0-58d4-931e-593d60355ee3": self._seed(
                "5fcfec7f-a8b0-58d4-931e-593d60355ee3", "usr_101",
                "犬の散歩をお願いしたい", "体調不良のため、小型犬の散歩を30分お願いしたいです。",
                "pet_support", 30, 1, 3, "2026-08-18T10:00:00+09:00",
                "2026-08-19T17:00:00+09:00",
            ),
            "39521aee-fc9b-5be6-9652-b3cf45d9107f": self._seed(
                "39521aee-fc9b-5be6-9652-b3cf45d9107f", "usr_301",
                "玄関前の雪かきを手伝ってほしい", "玄関から歩道までの雪かきをお願いします。",
                "snow_removal", 45, 2, 1, "2026-08-18T11:00:00+09:00",
                "2026-08-20T09:00:00+09:00",
            ),
        }

    @staticmethod
    def _seed(
        item_id: str, requester_id: str, title: str, description: str, category: str,
        minutes: int, helpers: int, version: int, created_at: str, scheduled_at: str,
    ) -> RequestRecord:
        return {
            "id": item_id, "requesterId": requester_id, "title": title,
            "description": description, "category": category, "riskLevel": "medium",
            "areaCode": "AREA-001", "areaLabel": "大学周辺・約1km", "distanceKm": 1.0,
            "acceptedHelpers": 0, "scheduledAt": scheduled_at,
            "estimatedMinutes": minutes, "requiredHelpers": helpers, "status": "published",
            "version": version, "warnings": [], "createdAt": created_at, "updatedAt": created_at,
            "_requesterVerificationStatus": {
                "usr_101": "approved", "usr_301": "unverified",
            }.get(requester_id, "unverified"),
        }

    async def list(self, actor: CurrentUser, *, category: str | None,
                   area_code: str | None, limit: int,
                   cursor: RequestCursor | None = None,
                   scheduled_from: datetime | None = None,
                   scheduled_to: datetime | None = None,
                   required_helpers: int | None = None,
                   max_distance_km: float | None = None,
                   verification_status: str | None = None,
                   blocked_requester_ids: Sequence[str] | None = None) -> list[RequestRecord]:
        del actor
        blocked_requester_ids = blocked_requester_ids or ()
        items = [item for item in self._items.values() if item["status"] == "published"]
        if category is not None:
            items = [item for item in items if item["category"] == category]
        if area_code is not None:
            items = [item for item in items if item["areaCode"] == area_code]
        items = [
            item for item in items
            if _matches_list_filters(
                item,
                scheduled_from=scheduled_from,
                scheduled_to=scheduled_to,
                required_helpers=required_helpers,
                max_distance_km=max_distance_km,
                verification_status=verification_status,
                blocked_requester_ids=blocked_requester_ids,
            )
        ]
        items.sort(
            key=lambda item: (_parse_timestamp(item["createdAt"]), item["id"]),
            reverse=True,
        )
        if cursor is not None:
            marker = self._items.get(cursor.request_id)
            if marker is None or _parse_timestamp(marker["createdAt"]) != cursor.created_at:
                raise InvalidCursor("cursor request does not exist")
            items = [
                item for item in items
                if (_parse_timestamp(item["createdAt"]), item["id"])
                < (cursor.created_at, cursor.request_id)
            ]
        return [_public_record(item) for item in items[:limit]]

    async def get(self, actor: CurrentUser, request_id: str) -> RequestRecord | None:
        del actor
        item = self._items.get(request_id)
        return _public_record(item) if item else None

    async def create(self, actor: CurrentUser, values: dict[str, Any]) -> RequestRecord:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        item = {
            "id": str(uuid.uuid4()), "requesterId": actor.user_id,
            **deepcopy(values), "areaLabel": "大学周辺・約1km", "distanceKm": 1.0,
            "acceptedHelpers": 0, "status": "draft", "version": 1,
            "warnings": [], "createdAt": now, "updatedAt": now,
            "_requesterVerificationStatus": actor.verification_status,
        }
        self._items[item["id"]] = item
        return _public_record(item)

    async def update(self, actor: CurrentUser, request_id: str, expected_version: int,
                     changes: dict[str, Any]) -> RequestRecord | None:
        del actor
        item = self._items.get(request_id)
        if item is None or item["version"] != expected_version:
            return None
        item.update(deepcopy(changes))
        item["version"] += 1
        item["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return _public_record(item)

    async def cancel(
        self, actor: CurrentUser, request_id: str, expected_version: int
    ) -> bool:
        return await self.set_status(
            actor, request_id, "cancelled", expected_version=expected_version,
        )

    async def set_status(self, actor: CurrentUser, request_id: str, status: str,
                         *, expected_version: int | None = None,
                         bump_version: bool = True) -> bool:
        del actor
        item = self._items.get(request_id)
        if item is None or (expected_version is not None and item["version"] != expected_version):
            return False
        item["status"] = status
        if bump_version:
            item["version"] += 1
        item["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return True

    async def reset(self) -> None:
        self.reset_sync()


class PostgresRequestRepository:
    _SELECT = """
        select r.id, r.title, r.original_text, r.category_id, r.risk_level,
               r.area_code, r.scheduled_at, r.estimated_minutes, r.required_helpers,
               r.status, r.version, r.created_at, r.updated_at,
               app.auth_subject_of(r.requester_id) as requester_auth_subject,
               app.verification_status_of(r.requester_id) as requester_verification_status,
               (select count(*) from matches m where m.request_id = r.id) as accepted_helpers
          from requests r
    """

    async def list(self, actor: CurrentUser, *, category: str | None,
                   area_code: str | None, limit: int,
                   cursor: RequestCursor | None = None,
                   scheduled_from: datetime | None = None,
                   scheduled_to: datetime | None = None,
                   required_helpers: int | None = None,
                   max_distance_km: float | None = None,
                   verification_status: str | None = None,
                   blocked_requester_ids: Sequence[str] | None = None) -> list[RequestRecord]:
        async with actor_connection(actor) as conn:
            blocked_requester_ids = list(blocked_requester_ids or ())
            cursor_id = None
            if cursor is not None:
                try:
                    cursor_id = uuid.UUID(cursor.request_id)
                except ValueError as exc:
                    raise InvalidCursor("cursor id is not a UUID") from exc
                marker = await conn.fetchrow(
                    "select created_at from requests where id = $1", cursor_id
                )
                if marker is None or _parse_timestamp(_iso(marker["created_at"])) != cursor.created_at:
                    raise InvalidCursor("cursor request does not exist")
            rows = await conn.fetch(
                self._SELECT + """
                 where r.status = 'published'
                   and ($1::text is null or r.category_id = $1)
                   and ($2::text is null or r.area_code = $2)
                   and ($3::timestamptz is null or r.scheduled_at >= $3::timestamptz)
                   and ($4::timestamptz is null or r.scheduled_at <= $4::timestamptz)
                   and ($5::integer is null or r.required_helpers = $5::integer)
                   and ($6::double precision is null or 1.0 <= $6::double precision)
                   and ($7::verification_status is null
                        or app.verification_status_of(r.requester_id) = $7::verification_status)
                   and not app.is_blocked_pair(r.requester_id, app.current_actor())
                   and not (app.auth_subject_of(r.requester_id) = any($8::text[]))
                   and ($9::timestamptz is null
                        or (r.created_at, r.id) < ($9::timestamptz, $10::uuid))
                 order by r.created_at desc, r.id desc limit $11
                """, category, area_code,
                 _normalise_datetime(scheduled_from) if scheduled_from else None,
                 _normalise_datetime(scheduled_to) if scheduled_to else None,
                 required_helpers, max_distance_km, verification_status,
                 blocked_requester_ids,
                 cursor.created_at if cursor else None, cursor_id, limit,
            )
        return [_row_to_record(row) for row in rows]

    async def get(self, actor: CurrentUser, request_id: str) -> RequestRecord | None:
        try:
            parsed_id = uuid.UUID(request_id)
        except ValueError:
            return None
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(self._SELECT + " where r.id = $1", parsed_id)
        return _row_to_record(row) if row else None

    async def create(self, actor: CurrentUser, values: dict[str, Any]) -> RequestRecord:
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(
                """insert into requests (
                       requester_id, title, original_text, category_id, risk_level,
                       area_code, scheduled_at, estimated_minutes, required_helpers
                   ) values (app.current_actor(), $1, $2, $3, $4, $5, $6, $7, $8)
                   returning id, title, original_text, category_id, risk_level, area_code,
                     scheduled_at, estimated_minutes, required_helpers, status, version,
                     created_at, updated_at""",
                values["title"], values["description"], values["category"], values["riskLevel"],
                values["areaCode"], datetime.fromisoformat(values["scheduledAt"]),
                values["estimatedMinutes"], values["requiredHelpers"],
            )
        return _row_to_record({**dict(row), "requester_auth_subject": actor.user_id,
                               "accepted_helpers": 0})

    async def update(self, actor: CurrentUser, request_id: str, expected_version: int,
                     changes: dict[str, Any]) -> RequestRecord | None:
        async with actor_connection(actor) as conn:
            updated = await conn.fetchval(
                "select app.update_request($1, $2, $3, $4, $5, $6, $7)", uuid.UUID(request_id),
                expected_version, changes.get("title"), changes.get("description"),
                datetime.fromisoformat(changes["scheduledAt"]) if "scheduledAt" in changes else None,
                changes.get("estimatedMinutes"), changes.get("requiredHelpers"),
            )
            if updated is None:
                return None
            row = await conn.fetchrow(self._SELECT + " where r.id = $1", uuid.UUID(request_id))
        return _row_to_record(row)

    async def cancel(
        self, actor: CurrentUser, request_id: str, expected_version: int
    ) -> bool:
        return await self.set_status(
            actor, request_id, "cancelled", expected_version=expected_version,
        )

    async def set_status(self, actor: CurrentUser, request_id: str, status: str,
                         *, expected_version: int | None = None,
                         bump_version: bool = True) -> bool:
        async with actor_connection(actor) as conn:
            updated = await conn.fetchval(
                "select app.set_request_status($1, $2::request_status, $3, $4)",
                uuid.UUID(request_id), status, expected_version, bump_version,
            )
        return updated is not None

    async def reset(self) -> None:
        from app.db import admin_connection
        async with admin_connection() as conn:
            await conn.execute("select app.mock_reset_requests()")


request_repository: RequestRepository = (
    PostgresRequestRepository()
    if settings.request_repository == "postgres"
    else MemoryRequestRepository()
)


def get_request_repository() -> RequestRepository:
    return request_repository
