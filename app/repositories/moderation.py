"""Privileged moderation operations. All writes are audited by the repository."""
from __future__ import annotations

import json
from typing import Any, Protocol

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings


class ModerationError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ModerationRepository(Protocol):
    async def list_verifications(self, actor: CurrentUser) -> list[dict[str, Any]]: ...
    async def decide_verification(self, actor: CurrentUser, item_id: str, decision: str, note: str | None) -> dict[str, Any]: ...
    async def list_reports(self, actor: CurrentUser) -> list[dict[str, Any]]: ...
    async def decide_report(self, actor: CurrentUser, item_id: str, status: str, note: str) -> dict[str, Any]: ...
    async def set_user_status(self, actor: CurrentUser, user_id: str, status: str, reason: str) -> None: ...
    async def list_audits(self, actor: CurrentUser) -> list[dict[str, Any]]: ...


class MemoryModerationRepository:
    async def list_verifications(self, actor):
        from app.cruds import main as r
        return sorted(r.verifications.values(), key=lambda x: x["createdAt"], reverse=True)
    async def decide_verification(self, actor, item_id, decision, note):
        from app.cruds import main as r
        item = r.verifications.get(item_id)
        if not item: raise ModerationError("VERIFICATION_NOT_FOUND")
        if item["status"] != "pending": raise ModerationError("VERIFICATION_STATE_CONFLICT")
        item.update(status=decision, reviewedAt=r.now_iso(), deletionDueAt=r.now_iso())
        r.users_store[item["userId"]]["verificationStatus"] = decision
        r.record_audit_event(actor_id=actor.user_id, event_type=f"verification_{decision}", target_type="verification_request", target_id=item_id, detail={"note": note} if note else {})
        return item
    async def list_reports(self, actor):
        from app.cruds import main as r
        return sorted(r.reports.values(), key=lambda x: x["createdAt"], reverse=True)
    async def decide_report(self, actor, item_id, status, note):
        from app.cruds import main as r
        item = r.reports.get(item_id)
        if not item: raise ModerationError("REPORT_NOT_FOUND")
        item["status"] = status
        r.record_audit_event(actor_id=actor.user_id, event_type=f"report_{status}", target_type="report", target_id=item_id, detail={"note": note})
        return item
    async def set_user_status(self, actor, user_id, status, reason):
        from app.cruds import main as r
        if user_id not in r.users_store: raise ModerationError("USER_NOT_FOUND")
        if user_id == actor.user_id: raise ModerationError("SELF_STATUS_CHANGE_FORBIDDEN")
        r.users_store[user_id]["status"] = status
        r.record_audit_event(actor_id=actor.user_id, event_type=f"user_{status}", target_type="user", target_id=user_id, detail={"reason": reason})
    async def list_audits(self, actor):
        from app.cruds import main as r
        return list(reversed(r.audit_logs))


class PostgresModerationRepository:
    async def _call(self, actor, sql, *args):
        async with actor_connection(actor) as conn: raw = await conn.fetchval(sql, *args)
        result = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if result.get("code") not in {"OK", "UPDATED"}: raise ModerationError(result.get("code", "MODERATION_FAILED"))
        return result
    async def list_verifications(self, actor): return (await self._call(actor, "select app.admin_list_verifications()"))["items"]
    async def decide_verification(self, actor, item_id, decision, note): return (await self._call(actor, "select app.admin_decide_verification($1,$2,$3)", item_id, decision, note))["item"]
    async def list_reports(self, actor): return (await self._call(actor, "select app.admin_list_reports()"))["items"]
    async def decide_report(self, actor, item_id, status, note): return (await self._call(actor, "select app.admin_decide_report($1,$2,$3)", item_id, status, note))["item"]
    async def set_user_status(self, actor, user_id, status, reason): await self._call(actor, "select app.admin_set_user_status($1,$2,$3)", user_id, status, reason)
    async def list_audits(self, actor): return (await self._call(actor, "select app.admin_list_audits()"))["items"]


_memory, _postgres = MemoryModerationRepository(), PostgresModerationRepository()
async def get_moderation_repository() -> ModerationRepository:
    return _postgres if settings.request_repository == "postgres" else _memory
