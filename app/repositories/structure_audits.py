"""依頼構造化の監査メタデータを保存するRepository境界。"""

import json
from typing import Protocol

from app.db import admin_connection
from app.settings import settings


class StructureAuditRepository(Protocol):
    async def save(self, audit: dict[str, str]) -> None: ...
    async def reset(self) -> None: ...


class MemoryStructureAuditRepository:
    """本文や個人情報を保持しない開発・テスト用Repository。"""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, str]] = {}

    async def save(self, audit: dict[str, str]) -> None:
        self.items[audit["id"]] = dict(audit)

    async def reset(self) -> None:
        self.items.clear()


class PostgresStructureAuditRepository:
    async def save(self, audit: dict[str, str]) -> None:
        async with admin_connection() as conn:
            await conn.execute(
                "select app.save_request_structure_audit($1::jsonb)",
                json.dumps(audit),
            )

    async def reset(self) -> None:
        async with admin_connection() as conn:
            await conn.execute("delete from request_structure_audits")


_memory = MemoryStructureAuditRepository()
_postgres = PostgresStructureAuditRepository()
structure_audit_repository: StructureAuditRepository = (
    _postgres if settings.request_repository == "postgres" else _memory
)


def get_structure_audit_repository() -> StructureAuditRepository:
    return structure_audit_repository
