from contextlib import asynccontextmanager

import pytest

from app.auth import CurrentUser
from app.repositories import reports as reports_module
from app.repositories.reports import PostgresReportRepository, ReportRepositoryError


ACTOR = CurrentUser(
    user_id="st_helper", role="member", status="active",
    email_verified=True, verification_status="approved",
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeConnection:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def fetchval(self, query, *args):
        self.calls.append((query, args))
        return self.result


@pytest.mark.anyio
async def test_postgres_report_repository_uses_actor_scoped_atomic_function(monkeypatch):
    connection = FakeConnection({
        "code": "CREATED", "id": "report-id", "reporterId": "st_helper",
        "targetType": "request", "targetId": "request-id",
        "reason": "dangerous_work", "description": "危険な作業が求められています。",
        "severity": "high", "status": "open", "createdAt": "2026-09-04T00:00:00Z",
    })

    @asynccontextmanager
    async def fake_actor_connection(actor):
        assert actor == ACTOR
        yield connection

    monkeypatch.setattr(reports_module, "actor_connection", fake_actor_connection)
    result = await PostgresReportRepository().create(
        ACTOR, target_type="request", target_id="request-id",
        reason="dangerous_work", description="危険な作業が求められています。",
    )

    assert result["severity"] == "high"
    assert connection.calls == [(
        "select app.create_report($1, $2, $3, $4)",
        ("request", "request-id", "dangerous_work", "危険な作業が求められています。"),
    )]


@pytest.mark.anyio
async def test_postgres_report_repository_maps_target_error(monkeypatch):
    connection = FakeConnection('{"code":"REPORT_TARGET_NOT_FOUND"}')

    @asynccontextmanager
    async def fake_actor_connection(actor):
        yield connection

    monkeypatch.setattr(reports_module, "actor_connection", fake_actor_connection)
    with pytest.raises(ReportRepositoryError) as raised:
        await PostgresReportRepository().create(
            ACTOR, target_type="request", target_id="missing",
            reason="fraud", description="存在しない依頼を通報しようとしました。",
        )
    assert raised.value.code == "REPORT_TARGET_NOT_FOUND"
