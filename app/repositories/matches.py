"""Match and chat persistence interfaces with Memory and Postgres backends."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from threading import Lock
from typing import Any, Callable, Protocol
import uuid

from app.auth import CurrentUser
from app.db import actor_connection
from app.repositories.applications import (
    MemoryApplicationRepository,
    get_application_repository,
)
from app.repositories.requests import MemoryRequestRepository, get_request_repository
from app.settings import settings


MatchRecord = dict[str, Any]
MessageRecord = dict[str, Any]
BlockChecker = Callable[[str, str], bool]


class MatchRepositoryError(Exception):
    """An expected matching conflict or authorization failure."""

    def __init__(self, code: str, current_version: int | None = None) -> None:
        self.code = code
        self.current_version = current_version
        super().__init__(code)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    }


def _message_to_record(row: Any) -> MessageRecord:
    moderation = row["moderation"]
    return {
        "id": str(row["id"]),
        "matchId": str(row["match_id"]),
        "senderId": row["sender_auth_subject"],
        "body": row["body"],
        "sentAt": _iso(row["sent_at"]),
        "readAt": _iso(row["read_at"]),
        "moderationStatus": {
            "clean": "allowed",
            "blocked": "hidden",
            "pending": "flagged",
        }.get(moderation, moderation),
    }


class MatchRepository(Protocol):
    async def select_application(
        self,
        actor: CurrentUser,
        application_id: str,
        request_id: str,
        expected_version: int,
    ) -> MatchRecord: ...

    async def get(self, actor: CurrentUser, match_id: str) -> MatchRecord | None: ...

    async def list_messages(
        self, actor: CurrentUser, match_id: str
    ) -> list[MessageRecord]: ...

    async def create_message(
        self, actor: CurrentUser, match_id: str, body: str
    ) -> MessageRecord: ...

    async def complete(
        self, actor: CurrentUser, match_id: str, actor_role: str
    ) -> MatchRecord: ...

    async def dispute(
        self, actor: CurrentUser, match_id: str, reason: str
    ) -> MatchRecord: ...

    async def reset(self) -> None: ...


class MemoryMatchRepository:
    """Atomic in-process implementation used by development and API tests."""

    def __init__(
        self,
        request_repository: MemoryRequestRepository,
        application_repository: MemoryApplicationRepository,
    ) -> None:
        self._request_repository = request_repository
        self._application_repository = application_repository
        self._matches: dict[str, MatchRecord] = {}
        self._messages: dict[str, list[MessageRecord]] = {}
        self._blocked: BlockChecker = lambda _first, _second: False
        self._lock = Lock()

    def configure_block_checker(self, checker: BlockChecker) -> None:
        self._blocked = checker

    @staticmethod
    def _role(match: MatchRecord, actor: CurrentUser) -> str | None:
        if match["requesterId"] == actor.user_id:
            return "requester"
        if match["helperId"] == actor.user_id:
            return "helper"
        return None

    async def select_application(
        self,
        actor: CurrentUser,
        application_id: str,
        request_id: str,
        expected_version: int,
    ) -> MatchRecord:
        with self._lock:
            request = self._request_repository._items.get(request_id)
            if request is None:
                raise MatchRepositoryError("REQUEST_NOT_FOUND")
            if request["requesterId"] != actor.user_id and actor.role != "admin":
                raise MatchRepositoryError("ROLE_FORBIDDEN")
            if request["version"] != expected_version:
                raise MatchRepositoryError(
                    "REQUEST_STATE_CONFLICT", request["version"]
                )
            application = self._application_repository._items.get(application_id)
            if application is None:
                raise MatchRepositoryError("APPLICATION_NOT_FOUND")
            if application["requestId"] != request_id:
                raise MatchRepositoryError("APPLICATION_REQUEST_MISMATCH")
            if application["status"] != "applied":
                raise MatchRepositoryError("APPLICATION_NOT_SELECTABLE")
            if request["status"] not in {"published", "matching"}:
                raise MatchRepositoryError(
                    "REQUEST_STATE_CONFLICT", request["version"]
                )
            if self._blocked(request["requesterId"], application["helperId"]):
                raise MatchRepositoryError("APPLICATION_NOT_SELECTABLE")

            selected_count = sum(
                item["requestId"] == request_id for item in self._matches.values()
            )
            if selected_count >= request["requiredHelpers"]:
                raise MatchRepositoryError("CAPACITY_REACHED")
            capacity_reached = selected_count + 1 >= request["requiredHelpers"]
            now = _now_iso()
            application["status"] = "selected"
            application["updatedAt"] = now
            if capacity_reached:
                for other in self._application_repository._items.values():
                    if other["requestId"] == request_id and other["status"] == "applied":
                        other["status"] = "not_selected"
                        other["updatedAt"] = now
            request["status"] = "matched" if capacity_reached else "matching"
            request["acceptedHelpers"] = selected_count + 1
            request["version"] += 1
            request["updatedAt"] = now
            match_id = str(uuid.uuid4())
            match = {
                "id": match_id,
                "requestId": request_id,
                "requesterId": request["requesterId"],
                "helperId": application["helperId"],
                "status": "matched",
                "requesterConfirmed": False,
                "helperConfirmed": False,
                "matchedAt": now,
                "completedAt": None,
                "disputeReason": None,
                "disputedAt": None,
            }
            self._matches[match_id] = match
            self._messages[match_id] = []
            return deepcopy(match)

    async def get(self, actor: CurrentUser, match_id: str) -> MatchRecord | None:
        match = self._matches.get(match_id)
        if match is None or (self._role(match, actor) is None and actor.role != "admin"):
            return None
        return deepcopy(match)

    async def list_messages(
        self, actor: CurrentUser, match_id: str
    ) -> list[MessageRecord]:
        with self._lock:
            match = self._matches.get(match_id)
            if match is None:
                raise MatchRepositoryError("MATCH_NOT_FOUND")
            if self._role(match, actor) is None and actor.role != "admin":
                raise MatchRepositoryError("ROLE_FORBIDDEN")
            now = _now_iso()
            visible: list[MessageRecord] = []
            for message in self._messages.get(match_id, []):
                if message["senderId"] != actor.user_id and message["readAt"] is None:
                    message["readAt"] = now
                if (
                    message["senderId"] != actor.user_id
                    and self._blocked(actor.user_id, message["senderId"])
                ):
                    continue
                visible.append(deepcopy(message))
            return visible

    async def create_message(
        self, actor: CurrentUser, match_id: str, body: str
    ) -> MessageRecord:
        with self._lock:
            match = self._matches.get(match_id)
            if match is None:
                raise MatchRepositoryError("MATCH_NOT_FOUND")
            if self._role(match, actor) is None:
                raise MatchRepositoryError("ROLE_FORBIDDEN")
            if self._blocked(match["requesterId"], match["helperId"]):
                raise MatchRepositoryError("MESSAGE_FORBIDDEN")
            item = {
                "id": str(uuid.uuid4()),
                "matchId": match_id,
                "senderId": actor.user_id,
                "body": body,
                "sentAt": _now_iso(),
                "readAt": None,
                "moderationStatus": "allowed",
            }
            self._messages.setdefault(match_id, []).append(item)
            return deepcopy(item)

    async def complete(
        self, actor: CurrentUser, match_id: str, actor_role: str
    ) -> MatchRecord:
        with self._lock:
            match = self._matches.get(match_id)
            if match is None:
                raise MatchRepositoryError("MATCH_NOT_FOUND")
            actual_role = self._role(match, actor)
            if actual_role is None:
                raise MatchRepositoryError("ROLE_FORBIDDEN")
            if actor_role != actual_role:
                raise MatchRepositoryError("ACTOR_ROLE_MISMATCH")
            if match["status"] not in {"matched", "completion_pending"}:
                raise MatchRepositoryError("MATCH_NOT_COMPLETABLE")
            confirmation_field = f"{actor_role}Confirmed"
            if match[confirmation_field]:
                raise MatchRepositoryError("MATCH_NOT_COMPLETABLE")

            match[confirmation_field] = True
            request = self._request_repository._items[match["requestId"]]
            if match["requesterConfirmed"] and match["helperConfirmed"]:
                match["status"] = "completed"
                match["completedAt"] = _now_iso()
                all_completed = all(
                    item["status"] == "completed"
                    for item in self._matches.values()
                    if item["requestId"] == match["requestId"]
                )
                request["status"] = "completed" if all_completed else "completion_pending"
            else:
                match["status"] = "completion_pending"
                request["status"] = "completion_pending"
            request["updatedAt"] = _now_iso()
            return deepcopy(match)

    async def dispute(
        self, actor: CurrentUser, match_id: str, reason: str
    ) -> MatchRecord:
        with self._lock:
            match = self._matches.get(match_id)
            if match is None:
                raise MatchRepositoryError("MATCH_NOT_FOUND")
            if self._role(match, actor) is None:
                raise MatchRepositoryError("ROLE_FORBIDDEN")
            if match["status"] in {"completed", "disputed"}:
                raise MatchRepositoryError("MATCH_NOT_DISPUTABLE")
            now = _now_iso()
            match.update(
                status="disputed", disputeReason=reason, disputedAt=now
            )
            request = self._request_repository._items[match["requestId"]]
            request["status"] = "disputed"
            request["updatedAt"] = now
            return deepcopy(match)

    async def reset(self) -> None:
        with self._lock:
            self._matches = {}
            self._messages = {}


class PostgresMatchRepository:
    _MATCH_SELECT = """
        select m.*, app.auth_subject_of(r.requester_id) requester_auth_subject,
               app.auth_subject_of(m.helper_id) helper_auth_subject,
               case when m.status = 'disputed' then m.updated_at end disputed_at
          from matches m join requests r on r.id = m.request_id
    """

    @staticmethod
    def _result(value: Any) -> dict[str, Any]:
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _uuid(value: str, not_found_code: str) -> uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise MatchRepositoryError(not_found_code) from exc

    async def select_application(
        self,
        actor: CurrentUser,
        application_id: str,
        request_id: str,
        expected_version: int,
    ) -> MatchRecord:
        parsed_application_id = self._uuid(application_id, "APPLICATION_NOT_FOUND")
        parsed_request_id = self._uuid(request_id, "REQUEST_NOT_FOUND")
        async with actor_connection(actor) as conn:
            result = self._result(
                await conn.fetchval(
                    "select app.select_application($1, $2, $3)",
                    parsed_application_id,
                    parsed_request_id,
                    expected_version,
                )
            )
            if result["code"] != "OK":
                raise MatchRepositoryError(
                    result["code"], result.get("currentVersion")
                )
            row = await conn.fetchrow(
                self._MATCH_SELECT + " where m.id = $1",
                uuid.UUID(result["matchId"]),
            )
        return _row_to_record(row)

    async def get(self, actor: CurrentUser, match_id: str) -> MatchRecord | None:
        try:
            parsed_id = uuid.UUID(match_id)
        except ValueError:
            return None
        async with actor_connection(actor) as conn:
            row = await conn.fetchrow(
                self._MATCH_SELECT + " where m.id = $1", parsed_id
            )
        return _row_to_record(row) if row else None

    async def list_messages(
        self, actor: CurrentUser, match_id: str
    ) -> list[MessageRecord]:
        parsed_id = self._uuid(match_id, "MATCH_NOT_FOUND")
        async with actor_connection(actor) as conn:
            result = self._result(
                await conn.fetchval("select app.mark_messages_read($1)", parsed_id)
            )
            if result["code"] != "OK":
                raise MatchRepositoryError(result["code"])
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
    ) -> MessageRecord:
        parsed_id = self._uuid(match_id, "MATCH_NOT_FOUND")
        async with actor_connection(actor) as conn:
            result = self._result(
                await conn.fetchval("select app.send_message($1, $2)", parsed_id, body)
            )
            if result["code"] != "OK":
                raise MatchRepositoryError(result["code"])
            row = await conn.fetchrow(
                """select msg.*, $2::text sender_auth_subject
                     from messages msg where msg.id = $1""",
                uuid.UUID(result["messageId"]),
                actor.user_id,
            )
        return _message_to_record(row)

    async def complete(
        self, actor: CurrentUser, match_id: str, actor_role: str
    ) -> MatchRecord:
        return await self._transition(actor, match_id, "complete_match", actor_role)

    async def dispute(
        self, actor: CurrentUser, match_id: str, reason: str
    ) -> MatchRecord:
        return await self._transition(actor, match_id, "dispute_match", reason)

    async def _transition(
        self, actor: CurrentUser, match_id: str, function: str, value: str
    ) -> MatchRecord:
        parsed_id = self._uuid(match_id, "MATCH_NOT_FOUND")
        async with actor_connection(actor) as conn:
            result = self._result(
                await conn.fetchval(f"select app.{function}($1, $2)", parsed_id, value)
            )
            if result["code"] != "OK":
                raise MatchRepositoryError(result["code"])
            row = await conn.fetchrow(
                self._MATCH_SELECT + " where m.id = $1", parsed_id
            )
        return _row_to_record(row)

    async def reset(self) -> None:
        # app.mock_reset_requests() removes matches/messages in the request reset.
        return None


if settings.request_repository == "postgres":
    match_repository: MatchRepository = PostgresMatchRepository()
else:
    configured_request_repository = get_request_repository()
    configured_application_repository = get_application_repository()
    if not isinstance(configured_request_repository, MemoryRequestRepository) or not isinstance(
        configured_application_repository, MemoryApplicationRepository
    ):
        raise RuntimeError("Memory repositories must be configured together")
    match_repository = MemoryMatchRepository(
        configured_request_repository, configured_application_repository
    )


def get_match_repository() -> MatchRepository:
    return match_repository


def configure_match_block_checker(checker: BlockChecker) -> None:
    if isinstance(match_repository, MemoryMatchRepository):
        match_repository.configure_block_checker(checker)
