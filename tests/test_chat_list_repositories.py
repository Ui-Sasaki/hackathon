from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncio

from app.auth import CurrentUser
from app.repositories import matches as matches_module
from app.repositories import messages as messages_module


ACTOR = CurrentUser(
    user_id="st_helper", role="member", status="active",
    email_verified=True, verification_status="approved",
)


def test_postgres_match_repository_maps_chat_list_summary(monkeypatch) -> None:
    class Connection:
        async def fetch(self, sql, *args):
            assert "app.list_own_chat_matches()" in sql
            assert args == ()
            return [{
                "id": "dddddddd-0000-0000-0000-000000000001",
                "request_id": "bbbbbbbb-0000-0000-0000-000000000001",
                "requester_auth_subject": "st_owner",
                "helper_auth_subject": "st_helper",
                "status": "matched",
                "requester_confirmed": False,
                "helper_confirmed": False,
                "matched_at": datetime(2026, 9, 4, tzinfo=timezone.utc),
                "completed_at": None,
                "dispute_reason": None,
                "disputed_at": None,
                "counterpart_display_name": "依頼 太郎",
                "request_title": "犬の散歩",
                "request_scheduled_at": datetime(2026, 9, 5, tzinfo=timezone.utc),
                "request_area_code": "AREA-001",
            }]

    @asynccontextmanager
    async def connection(actor):
        assert actor is ACTOR
        yield Connection()

    monkeypatch.setattr(matches_module, "actor_connection", connection)
    items = asyncio.run(matches_module.PostgresMatchRepository().list_for_user(ACTOR))

    assert items[0]["counterpartDisplayName"] == "依頼 太郎"
    assert items[0]["requestTitle"] == "犬の散歩"
    assert items[0]["helperId"] == "st_helper"


def test_postgres_message_peek_does_not_mark_messages_read(monkeypatch) -> None:
    class Connection:
        async def fetch(self, sql, match_id):
            assert "mark_match_messages_read" not in sql
            assert "app.match_is_visible" in sql
            return [{
                "id": "99999999-0000-0000-0000-000000000001",
                "match_id": match_id,
                "sender_auth_subject": "st_owner",
                "body": "よろしくお願いします",
                "moderation": "clean",
                "sent_at": datetime(2026, 9, 4, tzinfo=timezone.utc),
                "read_at": None,
            }]

    @asynccontextmanager
    async def connection(actor):
        assert actor is ACTOR
        yield Connection()

    monkeypatch.setattr(messages_module, "actor_connection", connection)
    items = asyncio.run(
        messages_module.PostgresMessageRepository().peek_for_match(
            ACTOR, "dddddddd-0000-0000-0000-000000000001",
        )
    )

    assert items[0]["body"] == "よろしくお願いします"
    assert items[0]["readAt"] is None
