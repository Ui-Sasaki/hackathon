"""大学メール確認チャレンジの永続化境界。"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4
import secrets

from app.auth import CurrentUser
from app.db import actor_connection
from app.settings import settings


class VerificationEmailRepository(Protocol):
    async def create(self, actor: CurrentUser, email: str, digest: str, challenge_id: str) -> dict: ...
    async def verify(self, actor: CurrentUser, challenge_id: str, digest: str) -> str: ...


class MemoryVerificationEmailRepository:
    def __init__(self): self.items: dict[str, dict[str, Any]] = {}
    async def create(self, actor, email, digest, challenge_id):
        now=datetime.now(timezone.utc)
        item={"id":challenge_id,"userId":actor.user_id,"email":email,"digest":digest,
              "attempts":0,"expiresAt":now+timedelta(minutes=10),"createdAt":now}
        self.items[challenge_id]=item; return item
    async def verify(self, actor, challenge_id, digest):
        item=self.items.get(challenge_id)
        if not item or item["userId"]!=actor.user_id: return "CHALLENGE_NOT_FOUND"
        if item["expiresAt"]<=datetime.now(timezone.utc): return "CODE_EXPIRED"
        if item["attempts"]>=5: return "TOO_MANY_ATTEMPTS"
        item["attempts"]+=1
        if not secrets.compare_digest(item["digest"],digest): return "INVALID_CODE"
        from app.cruds import main as runtime
        runtime.users_store[actor.user_id]["verificationStatus"]="approved"
        del self.items[challenge_id]; return "APPROVED"


class PostgresVerificationEmailRepository:
    async def create(self, actor,email,digest,challenge_id):
        async with actor_connection(actor) as conn:
            await conn.execute("select app.create_university_email_challenge($1::uuid,$2,$3)",challenge_id,email,digest)
        return {"id":challenge_id,"email":email}
    async def verify(self, actor,challenge_id,digest):
        async with actor_connection(actor) as conn:
            return await conn.fetchval("select app.verify_university_email_code($1::uuid,$2)",challenge_id,digest)


_memory=MemoryVerificationEmailRepository(); _postgres=PostgresVerificationEmailRepository()
def get_verification_email_repository():
    return _postgres if settings.request_repository=="postgres" else _memory
