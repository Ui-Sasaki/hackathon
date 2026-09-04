"""Chat message persistence interface plus Memory and Postgres implementations."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any, Protocol, Sequence
import uuid

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings


MessageRecord = dict[str, Any]


def _iso(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return value.isoformat().replace("+00:00", "Z")


def _row_to_record(row: Any) -> MessageRecord:
    moderation = {
        "clean": "allowed", "pending": "flagged",
        "flagged": "flagged", "blocked": "hidden",
    }
    return {
        "id": str(row["id"]),
        "matchId": str(row["match_id"]),
        "senderId": row["sender_auth_subject"],
        "body": row["body"],
        "sentAt": _iso(row["sent_at"]),
        "readAt": _iso(row["read_at"]),
        "moderationStatus": moderation[row["moderation"]],
    }


class MessageRepository(Protocol):
    async def peek_for_match(
        self, actor: CurrentUser, match_id: str, *, blocked_user_ids: Sequence[str] = ()
    ) -> list[MessageRecord]: ...

    async def list_for_match(
        self, actor: CurrentUser, match_id: str, *, blocked_user_ids: Sequence[str] = ()
    ) -> list[MessageRecord]: ...

    async def create(
        self, actor: CurrentUser, match_id: str, body: str,
        *, moderation_status: str = "allowed",
    ) -> MessageRecord | None: ...

    async def reset(self) -> None: ...


class MemoryMessageRepository:
    def __init__(self) -> None:
        self._items: dict[str, list[MessageRecord]] = {}

    def bind(self, items: dict[str, list[MessageRecord]]) -> None:
        self._items = items

    async def list_for_match(
        self, actor: CurrentUser, match_id: str, *, blocked_user_ids: Sequence[str] = ()
    ) -> list[MessageRecord]:
        result = []
        for item in self._items.get(match_id, []):
            if item["senderId"] in blocked_user_ids:
                continue
            if item["senderId"] != actor.user_id and item["readAt"] is None:
                item["readAt"] = _iso(datetime.now(timezone.utc))
            result.append(deepcopy(item))
        return result

    async def peek_for_match(
        self, actor: CurrentUser, match_id: str, *, blocked_user_ids: Sequence[str] = ()
    ) -> list[MessageRecord]:
        del actor
        return [
            deepcopy(item) for item in self._items.get(match_id, [])
            if item["senderId"] not in blocked_user_ids
        ]

    async def create(
        self, actor: CurrentUser, match_id: str, body: str,
        *, moderation_status: str = "allowed",
    ) -> MessageRecord:
        item = {
            "id": f"msg_{uuid.uuid4().hex[:8]}",
            "matchId": match_id,
            "senderId": actor.user_id,
            "body": body,
            "sentAt": _iso(datetime.now(timezone.utc)),
            "readAt": None,
            "moderationStatus": moderation_status,
        }
        self._items.setdefault(match_id, []).append(item)
        return deepcopy(item)

    async def reset(self) -> None:
        self._items.clear()


class PostgresMessageRepository:
    _SELECT = """select msg.id, msg.match_id, msg.body, msg.moderation,
                         msg.sent_at, msg.read_at,
                         app.auth_subject_of(msg.sender_id) as sender_auth_subject
                    from messages msg"""

    async def peek_for_match(
        self, actor: CurrentUser, match_id: str, *, blocked_user_ids: Sequence[str] = ()
    ) -> list[MessageRecord]:
        del actor, match_id, blocked_user_ids
        raise NotImplementedError("chat list persistence is not implemented")

    async def list_for_match(
        self, actor: CurrentUser, match_id: str, *, blocked_user_ids: Sequence[str] = ()
    ) -> list[MessageRecord]:
        del blocked_user_ids
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return []
        async with actor_connection(actor) as conn:
            await conn.fetchval("select app.mark_match_messages_read($1)", parsed_id)
            rows = await conn.fetch(
                self._SELECT + """
                 join matches m on m.id = msg.match_id
                 join requests r on r.id = m.request_id
                where msg.match_id = $1
                  and app.match_is_visible(m.id)
                order by msg.sent_at, msg.id""",
                parsed_id,
            )
        return [_row_to_record(row) for row in rows]

    async def create(
        self, actor: CurrentUser, match_id: str, body: str,
        *, moderation_status: str = "allowed",
    ) -> MessageRecord | None:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return None
        async with actor_connection(actor) as conn:
            database_moderation = "flagged" if moderation_status == "flagged" else "clean"
            raw = await conn.fetchval(
                "select app.send_match_message($1, $2, $3::moderation_status)",
                parsed_id, body, database_moderation,
            )
            result = json.loads(raw) if isinstance(raw, str) else dict(raw)
            if result.get("code") != "SENT":
                return None
            row = await conn.fetchrow(
                self._SELECT + " where msg.id = $1",
                uuid.UUID(result["messageId"]),
            )
        return _row_to_record(row) if row else None

    async def reset(self) -> None:
        return None


message_repository: MessageRepository = (
    PostgresMessageRepository()
    if settings.request_repository == "postgres"
    else MemoryMessageRepository()
)


def get_message_repository() -> MessageRepository:
    return message_repository
