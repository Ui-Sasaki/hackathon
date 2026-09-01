"""Upload session and stored image persistence interface plus a Memory implementation.

Storage、Postgres、RLS、削除期限はストレージ担当との合意事項のため、ここでは
Memory実装だけを提供する（`docs/cross-team-coordination.md` COORD-004）。
実装を差し替えても外へ出す値が変わらないよう、境界をこのProtocolで固定する。
"""

from __future__ import annotations

import secrets
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Protocol

UploadPurpose = Literal["profile_image", "verification_document"]
UploadRecord = dict[str, Any]
ImageRecord = dict[str, Any]

# 開始しただけで使われないアップロードを溜めないための有効期限。
UPLOAD_TTL_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class UploadRepository(Protocol):
    async def create_session(
        self, owner_id: str, purpose: UploadPurpose, content_type: str, byte_size: int
    ) -> UploadRecord: ...

    async def get_session(self, upload_id: str) -> UploadRecord | None: ...

    async def attach_content(
        self, upload_id: str, data: bytes, content_type: str
    ) -> UploadRecord | None: ...

    async def promote_to_image(
        self, upload_id: str, owner_id: str
    ) -> ImageRecord | None: ...

    async def get_image(self, image_id: str) -> ImageRecord | None: ...

    async def delete_image(self, image_id: str) -> bool: ...

    async def purge_expired(self) -> int: ...

    async def reset(self) -> None: ...


class MemoryUploadRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, UploadRecord] = {}
        self._images: dict[str, ImageRecord] = {}

    async def create_session(
        self, owner_id: str, purpose: UploadPurpose, content_type: str, byte_size: int
    ) -> UploadRecord:
        created_at = _now()
        session = {
            "id": str(uuid.uuid4()),
            "ownerId": owner_id,
            "purpose": purpose,
            "contentType": content_type,
            "declaredByteSize": byte_size,
            "status": "pending",
            "createdAt": _iso(created_at),
            "expiresAt": _iso(created_at + timedelta(minutes=UPLOAD_TTL_MINUTES)),
            # ストレージ内部キーはレスポンスへ出さない。差し替え先の実装が使う。
            "storageObjectKey": f"private/{purpose}/{uuid.uuid4()}",
            "data": None,
        }
        self._sessions[session["id"]] = session
        return deepcopy(session)

    async def get_session(self, upload_id: str) -> UploadRecord | None:
        session = self._sessions.get(upload_id)
        return deepcopy(session) if session else None

    async def attach_content(
        self, upload_id: str, data: bytes, content_type: str
    ) -> UploadRecord | None:
        session = self._sessions.get(upload_id)
        if session is None:
            return None
        session["data"] = data
        session["contentType"] = content_type
        session["byteSize"] = len(data)
        session["status"] = "stored"
        return deepcopy(session)

    async def promote_to_image(
        self, upload_id: str, owner_id: str
    ) -> ImageRecord | None:
        """検証済みのアップロードを、参照可能な画像として確定する。"""
        session = self._sessions.get(upload_id)
        if session is None or session["data"] is None:
            return None
        image = {
            "id": str(uuid.uuid4()),
            "ownerId": owner_id,
            "purpose": session["purpose"],
            "contentType": session["contentType"],
            "byteSize": session["byteSize"],
            # 推測できない参照子。公開パスへ利用者IDやファイル名を出さないために使う。
            "viewToken": secrets.token_urlsafe(24),
            "storageObjectKey": session["storageObjectKey"],
            "data": session["data"],
            "createdAt": _iso(_now()),
        }
        self._images[image["id"]] = image
        # 確定したセッションは再利用させない。二重確定を防ぐ。
        session["status"] = "consumed"
        session["data"] = None
        return deepcopy(image)

    async def get_image(self, image_id: str) -> ImageRecord | None:
        image = self._images.get(image_id)
        return deepcopy(image) if image else None

    async def find_image_by_token(self, view_token: str) -> ImageRecord | None:
        for image in self._images.values():
            if secrets.compare_digest(image["viewToken"], view_token):
                return deepcopy(image)
        return None

    async def delete_image(self, image_id: str) -> bool:
        return self._images.pop(image_id, None) is not None

    async def purge_expired(self) -> int:
        """期限切れの未確定アップロードを回収する。本番では定期処理から呼ぶ。"""
        now = _now()
        expired = [
            upload_id
            for upload_id, session in self._sessions.items()
            if session["status"] != "consumed"
            and datetime.fromisoformat(session["expiresAt"].replace("Z", "+00:00")) <= now
        ]
        for upload_id in expired:
            del self._sessions[upload_id]
        return len(expired)

    async def reset(self) -> None:
        self._sessions = {}
        self._images = {}


_upload_repository = MemoryUploadRepository()


def get_upload_repository() -> UploadRepository:
    return _upload_repository
