"""Match persistence for production PostgreSQL operations."""

from __future__ import annotations

import json
from typing import Any
import uuid

from app.auth import CurrentUser
from app.db import actor_connection


MatchRecord = dict[str, Any]


class MatchSelectionError(Exception):
    def __init__(self, code: str, current_version: int | None = None) -> None:
        self.code = code
        self.current_version = current_version
        super().__init__(code)


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
        "disputedAt": _iso(row.get("disputed_at")),
    }


def _message_to_record(row: Any) -> dict[str, Any]:
    moderation = row["moderation"]
    return {
        "id": str(row["id"]),
        "matchId": str(row["match_id"]),
        "senderId": row["sender_auth_subject"],
        "body": row["body"],
        "sentAt": _iso(row["sent_at"]),
        "readAt": _iso(row["read_at"]),
        "moderationStatus": {
            "clean": "allowed", "blocked": "hidden", "pending": "flagged",
        }.get(moderation, moderation),
    }


class PostgresMatchRepository:
    _MATCH_SELECT = """select m.*, app.auth_subject_of(r.requester_id) requester_auth_subject,
                               app.auth_subject_of(m.helper_id) helper_auth_subject,
                               case when m.status = 'disputed' then m.updated_at end disputed_at
                          from matches m join requests r on r.id = m.request_id"""

    async def select_application(
        self,
        actor: CurrentUser,
        application_id: str,
        request_id: str,
        expected_version: int,
    ) -> MatchRecord:
        try:
            parsed_application_id = uuid.UUID(application_id)
            parsed_request_id = uuid.UUID(request_id)
        except ValueError as exc:
            raise MatchSelectionError("APPLICATION_NOT_FOUND") from exc

        async with actor_connection(actor) as conn:
            result = await conn.fetchval(
                "select app.select_application($1, $2, $3)",
                parsed_application_id,
                parsed_request_id,
                expected_version,
            )
            if isinstance(result, str):
                result = json.loads(result)
            if result["code"] != "OK":
                raise MatchSelectionError(result["code"], result.get("currentVersion"))
            row = await conn.fetchrow(
                self._MATCH_SELECT + " where m.id = $1", uuid.UUID(result["matchId"]),
            )
        return _row_to_record(row)

    async def get(self, actor: CurrentUser, match_id: str) -> MatchRecord | None:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return None
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(self._MATCH_SELECT + " where m.id = $1", parsed_id)
        return _row_to_record(row) if row else None

    async def list_messages(self, actor: CurrentUser, match_id: str) -> list[dict[str, Any]]:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return []
        async with actor_connection(actor) as conn:
            await conn.execute("select app.mark_messages_read($1)", parsed_id)
            rows = await conn.fetch(
                """select msg.*, app.auth_subject_of(msg.sender_id) sender_auth_subject
                     from messages msg
                    where msg.match_id = $1
                      and (msg.sender_id = app.current_actor()
                           or not app.is_blocked_pair(msg.sender_id, app.current_actor()))
                    order by msg.sent_at, msg.id""",
                parsed_id,
            )
        return [_message_to_record(row) for row in rows]

    async def create_message(
        self, actor: CurrentUser, match_id: str, body: str
    ) -> dict[str, Any] | None:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return None
        async with actor_connection(actor) as conn:
            message_id = await conn.fetchval(
                "select app.send_message($1, $2)", parsed_id, body,
            )
            if message_id is None:
                return None
            row = await conn.fetchrow(
                """select msg.*, $2::text sender_auth_subject
                     from messages msg where msg.id = $1""",
                message_id, actor.user_id,
            )
        return _message_to_record(row) if row else None

    async def complete(
        self, actor: CurrentUser, match_id: str, actor_role: str
    ) -> MatchRecord:
        return await self._transition(actor, match_id, "complete", actor_role)

    async def dispute(
        self, actor: CurrentUser, match_id: str, reason: str
    ) -> MatchRecord:
        return await self._transition(actor, match_id, "dispute", reason)

    async def _transition(
        self, actor: CurrentUser, match_id: str, operation: str, value: str
    ) -> MatchRecord:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError as exc:
            raise MatchSelectionError("MATCH_NOT_FOUND") from exc
        function = "complete_match" if operation == "complete" else "dispute_match"
        async with actor_connection(actor) as conn:
            result = await conn.fetchval(f"select app.{function}($1, $2)", parsed_id, value)
            if isinstance(result, str):
                result = json.loads(result)
            if result["code"] != "OK":
                raise MatchSelectionError(result["code"])
            row = await conn.fetchrow(self._MATCH_SELECT + " where m.id = $1", parsed_id)
        return _row_to_record(row)


postgres_match_repository = PostgresMatchRepository()
