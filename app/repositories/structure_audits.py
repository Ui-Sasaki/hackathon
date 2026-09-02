"""依頼構造化の監査メタデータを保存するRepository境界。"""

from typing import Protocol


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


structure_audit_repository = MemoryStructureAuditRepository()


def get_structure_audit_repository() -> StructureAuditRepository:
    return structure_audit_repository
