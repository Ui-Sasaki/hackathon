"""Match persistence interface plus Memory and Postgres implementations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol
import uuid

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings


MatchRecord = dict[str, Any]


def _iso(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return value.isoformat().replace("+00:00", "Z")


def _row_to_record(row: Any) -> MatchRecord:
    return {
        "id": str(row["id"]),
        "requestId": str(row["request_id"]),
        "requesterId": row["requester_auth_subject"],
        "helperId": row["helper_auth_subject"],
        "status": row["status"],
        "requesterConfirmed": row["requester_confirmed"],
        "helperConfirmed": row["helper_confirmed"],
        "matchedAt": _iso(row["matched_at"]),
        "completedAt": _iso(row["completed_at"]),
        "disputeReason": row["dispute_reason"],
        "disputedAt": _iso(row["disputed_at"]),
        "version": 1,
    }


class MatchRepository(Protocol):
    async def list_for_user(self, actor: CurrentUser) -> list[MatchRecord]: ...

    async def get(self, actor: CurrentUser, match_id: str) -> MatchRecord | None: ...

    async def create(self, actor: CurrentUser, values: MatchRecord) -> MatchRecord: ...

    async def complete(self, actor: CurrentUser, match_id: str) -> str: ...

    async def dispute(self, actor: CurrentUser, match_id: str, reason: str) -> str: ...

    async def reset(self) -> None: ...


class MemoryMatchRepository:
    def __init__(self) -> None:
        self._items: dict[str, MatchRecord] = {}

    async def get(self, actor: CurrentUser, match_id: str) -> MatchRecord | None:
        del actor
        item = self._items.get(match_id)
        return deepcopy(item) if item else None

    async def list_for_user(self, actor: CurrentUser) -> list[MatchRecord]:
        items = [
            deepcopy(item) for item in self._items.values()
            if actor.user_id in {item["requesterId"], item["helperId"]}
        ]
        return sorted(
            items, key=lambda item: (item["matchedAt"], item["id"]), reverse=True,
        )

    async def create(self, actor: CurrentUser, values: MatchRecord) -> MatchRecord:
        del actor
        # The legacy completion/dispute endpoints still mutate the in-process
        # record in place; retain the same object until those endpoints move to
        # repository methods in dbtodo 04.
        self._items[values["id"]] = values
        return deepcopy(values)

    async def reset(self) -> None:
        self._items.clear()

    async def complete(self, actor: CurrentUser, match_id: str) -> str:
        item = self._items.get(match_id)
        if item is None:
            return "MATCH_NOT_FOUND"
        if item["status"] not in {"matched", "completion_pending"}:
            return "MATCH_NOT_COMPLETABLE"
        key = "requesterConfirmed" if item["requesterId"] == actor.user_id else "helperConfirmed"
        if item.get(key):
            return "COMPLETION_ALREADY_CONFIRMED"
        item[key] = True
        item["status"] = "completed" if item["requesterConfirmed"] and item["helperConfirmed"] else "completion_pending"
        if item["status"] == "completed":
            from datetime import datetime, timezone
            item["completedAt"] = _iso(datetime.now(timezone.utc))
        return "CONFIRMED"

    async def dispute(self, actor: CurrentUser, match_id: str, reason: str) -> str:
        del actor
        item = self._items.get(match_id)
        if item is None:
            return "MATCH_NOT_FOUND"
        if item["status"] in {"completed", "disputed", "cancelled"}:
            return "MATCH_NOT_DISPUTABLE"
        item["status"] = "disputed"
        item["disputeReason"] = reason
        from datetime import datetime, timezone
        item["disputedAt"] = _iso(datetime.now(timezone.utc))
        return "DISPUTED"

    def reset_sync(self) -> None:
        self._items.clear()


class PostgresMatchRepository:
    async def list_for_user(self, actor: CurrentUser) -> list[MatchRecord]:
        async with actor_connection(actor) as conn:
            rows = await conn.fetch("select * from app.list_own_chat_matches()")
        result = []
        for row in rows:
            item = _row_to_record(row)
            item.update({
                "counterpartDisplayName": row["counterpart_display_name"],
                "requestTitle": row["request_title"],
                "requestScheduledAt": _iso(row["request_scheduled_at"]),
                "requestAreaCode": row["request_area_code"],
            })
            result.append(item)
        return result

    async def get(self, actor: CurrentUser, match_id: str) -> MatchRecord | None:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return None
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(
                """select m.id, m.request_id, m.status, m.requester_confirmed,
                          m.helper_confirmed, m.dispute_reason, m.matched_at,
                          m.completed_at, m.disputed_at,
                          app.auth_subject_of(r.requester_id) as requester_auth_subject,
                          app.auth_subject_of(m.helper_id) as helper_auth_subject
                     from matches m
                     join requests r on r.id = m.request_id
                    where m.id = $1
                      and app.match_is_visible(m.id)""",
                parsed_id,
            )
        return _row_to_record(row) if row else None

    async def create(self, actor: CurrentUser, values: MatchRecord) -> MatchRecord:
        del actor, values
        raise RuntimeError("matches are created by app.select_application")

    async def _transition(self, actor: CurrentUser, sql: str, *args: Any) -> str:
        async with actor_connection(actor) as conn:
            raw = await conn.fetchval(sql, *args)
        import json
        result = json.loads(raw) if isinstance(raw, str) else dict(raw)
        return str(result.get("code", "MATCH_STATE_CONFLICT"))

    async def complete(self, actor: CurrentUser, match_id: str) -> str:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return "MATCH_NOT_FOUND"
        return await self._transition(actor, "select app.complete_match($1)", parsed_id)

    async def dispute(self, actor: CurrentUser, match_id: str, reason: str) -> str:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return "MATCH_NOT_FOUND"
        return await self._transition(
            actor, "select app.dispute_match($1, $2)", parsed_id, reason,
        )

    async def reset(self) -> None:
        return None


match_repository: MatchRepository = (
    PostgresMatchRepository()
    if settings.request_repository == "postgres"
    else MemoryMatchRepository()
)


def get_match_repository() -> MatchRepository:
    return match_repository
