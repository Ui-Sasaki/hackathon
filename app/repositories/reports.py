"""Safety-report persistence with identical Memory and Postgres contracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings


ReportRecord = dict[str, Any]


class ReportRepositoryError(Exception):
    """A report target is absent or cannot be reported by this actor."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ReportRepository(Protocol):
    async def create(
        self, actor: CurrentUser, *, target_type: str, target_id: str,
        reason: str, description: str,
    ) -> ReportRecord: ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryReportRepository:
    async def create(
        self, actor: CurrentUser, *, target_type: str, target_id: str,
        reason: str, description: str,
    ) -> ReportRecord:
        # Keep the test/development path on the same boundary as Postgres. The
        # legacy stores remain the source of fixture data until the related
        # repositories are made persistent.
        from app.cruds import main as runtime

        if target_type == "user":
            exists = target_id in runtime.users_store
        elif target_type == "request":
            request_repository = await runtime.request_repository_dependency()
            exists = await request_repository.get(actor, target_id) is not None
        elif target_type == "match":
            exists = target_id in runtime.matches
        elif target_type == "message":
            exists = any(
                item["id"] == target_id
                for items in runtime.messages.values() for item in items
            )
        else:  # review
            exists = target_id in runtime.reviews
        if not exists:
            raise ReportRepositoryError("REPORT_TARGET_NOT_FOUND")

        severity = "high" if reason in {"fraud", "dangerous_work"} else "medium"
        item: ReportRecord = {
            "id": runtime.new_id("report"),
            "reporterId": actor.user_id,
            "targetType": target_type,
            "targetId": target_id,
            "reason": reason,
            "description": description,
            "severity": severity,
            "status": "open",
            "createdAt": _now_iso(),
        }
        runtime.reports[item["id"]] = item
        runtime.record_audit_event(
            actor_id=actor.user_id,
            event_type="report_created",
            target_type=target_type,
            target_id=target_id,
            detail={"reportId": item["id"], "severity": severity},
        )
        if severity == "high" and target_type == "request":
            request_repository = await runtime.request_repository_dependency()
            await request_repository.set_status(actor, target_id, "suspended")
            runtime.record_audit_event(
                actor_id=actor.user_id,
                event_type="request_auto_suspended",
                target_type="request",
                target_id=target_id,
                detail={"reportId": item["id"]},
            )
        return item


class PostgresReportRepository:
    async def create(
        self, actor: CurrentUser, *, target_type: str, target_id: str,
        reason: str, description: str,
    ) -> ReportRecord:
        async with actor_connection(actor) as conn:
            raw = await conn.fetchval(
                "select app.create_report($1, $2, $3, $4)",
                target_type, target_id, reason, description,
            )
        result = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if result.get("code") != "CREATED":
            raise ReportRepositoryError(str(result.get("code", "REPORT_TARGET_NOT_FOUND")))
        return {
            "id": result["id"], "reporterId": result["reporterId"],
            "targetType": result["targetType"], "targetId": result["targetId"],
            "reason": result["reason"], "description": result["description"],
            "severity": result["severity"], "status": result["status"],
            "createdAt": result["createdAt"],
        }


_memory = MemoryReportRepository()
_postgres = PostgresReportRepository()


async def get_report_repository() -> ReportRepository:
    return _postgres if settings.request_repository == "postgres" else _memory
