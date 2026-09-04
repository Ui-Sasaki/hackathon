from contextlib import asynccontextmanager

import pytest

from app.auth import CurrentUser
from app.repositories import request_dismissals as dismissals_module
from app.repositories import saved_requests as saved_module
from app.repositories import structure_audits as audits_module
from app.repositories import user_settings as settings_module
from app.repositories.request_dismissals import PostgresRequestDismissalRepository
from app.repositories.saved_requests import PostgresSavedRequestRepository
from app.repositories.structure_audits import PostgresStructureAuditRepository
from app.repositories.user_settings import PostgresUserSettingsRepository


ACTOR = CurrentUser(
    user_id="st_owner", role="member", status="active",
    email_verified=True, verification_status="approved",
)
REQUEST_ID = "5fcfec7f-a8b0-58d4-931e-593d60355ee3"


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeConnection:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
        self.calls = []

    async def fetchrow(self, query, *args):
        self.calls.append(("fetchrow", query, args))
        return self.row

    async def fetch(self, query, *args):
        self.calls.append(("fetch", query, args))
        return self.rows

    async def execute(self, query, *args):
        self.calls.append(("execute", query, args))
        return "OK"


@pytest.mark.anyio
async def test_postgres_user_settings_uses_actor_scoped_upsert(monkeypatch):
    connection = FakeConnection(row={
        "notifications_enabled": True,
        "location_enabled": False,
        "font_size": "large",
    })

    @asynccontextmanager
    async def fake_actor_connection(actor):
        assert actor == ACTOR
        yield connection

    monkeypatch.setattr(settings_module, "actor_connection", fake_actor_connection)
    result = await PostgresUserSettingsRepository().update(
        ACTOR, {"locationEnabled": False, "fontSize": "large"}
    )

    assert result == {
        "notificationsEnabled": True,
        "locationEnabled": False,
        "fontSize": "large",
    }
    method, query, args = connection.calls[0]
    assert method == "fetchrow"
    assert "user_settings" in query
    assert "app.current_actor()" in query
    assert args == (None, False, "large")


@pytest.mark.anyio
async def test_postgres_saved_requests_are_actor_scoped(monkeypatch):
    connection = FakeConnection(rows=[{"request_id": REQUEST_ID}])

    @asynccontextmanager
    async def fake_actor_connection(actor):
        assert actor == ACTOR
        yield connection

    monkeypatch.setattr(saved_module, "actor_connection", fake_actor_connection)
    repository = PostgresSavedRequestRepository()

    assert await repository.list_ids(ACTOR) == {REQUEST_ID}
    await repository.save(ACTOR, REQUEST_ID)
    await repository.remove(ACTOR, REQUEST_ID)

    assert all("app.current_actor()" in call[1] for call in connection.calls)


@pytest.mark.anyio
async def test_postgres_request_dismissals_are_actor_scoped(monkeypatch):
    connection = FakeConnection(rows=[{"request_id": REQUEST_ID}])

    @asynccontextmanager
    async def fake_actor_connection(actor):
        assert actor == ACTOR
        yield connection

    monkeypatch.setattr(dismissals_module, "actor_connection", fake_actor_connection)
    repository = PostgresRequestDismissalRepository()

    assert await repository.list_ids(ACTOR) == {REQUEST_ID}
    await repository.dismiss(ACTOR, REQUEST_ID)
    await repository.restore(ACTOR, REQUEST_ID)

    assert all("app.current_actor()" in call[1] for call in connection.calls)


@pytest.mark.anyio
async def test_postgres_structure_audit_uses_definer_function(monkeypatch):
    connection = FakeConnection()

    @asynccontextmanager
    async def fake_admin_connection():
        yield connection

    monkeypatch.setattr(audits_module, "admin_connection", fake_admin_connection)
    await PostgresStructureAuditRepository().save({
        "id": "structure_123",
        "modelName": "claude-test",
        "promptVersion": "request-structure-v1",
        "processedAt": "2026-09-04T00:00:00+00:00",
        "schemaVersion": "structured-request-v1",
    })

    assert connection.calls[0][0] == "execute"
    assert connection.calls[0][1] == "select app.save_request_structure_audit($1::jsonb)"
    assert "claude-test" in connection.calls[0][2][0]
