from contextlib import asynccontextmanager

import pytest

from app.auth import CurrentUser
from app.repositories import blocks as blocks_module
from app.repositories.blocks import BlockRepositoryError, PostgresBlockRepository


ACTOR = CurrentUser(
    user_id="st_owner", role="member", status="active",
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
async def test_postgres_block_repository_uses_actor_scoped_function(monkeypatch):
    connection = FakeConnection({
        "code": "OK", "userId": "st_helper", "blocked": True,
        "updatedAt": "2026-09-04T00:00:00.000000Z",
    })

    @asynccontextmanager
    async def fake_actor_connection(actor):
        assert actor == ACTOR
        yield connection

    monkeypatch.setattr(blocks_module, "actor_connection", fake_actor_connection)
    result = await PostgresBlockRepository().set(ACTOR, "st_helper", True)

    assert result["userId"] == "st_helper"
    assert result["blocked"] is True
    assert connection.calls == [
        ("select app.set_own_block($1, $2)", ("st_helper", True))
    ]


@pytest.mark.anyio
async def test_postgres_block_repository_maps_database_error(monkeypatch):
    connection = FakeConnection('{"code":"SELF_BLOCK_NOT_ALLOWED"}')

    @asynccontextmanager
    async def fake_actor_connection(actor):
        yield connection

    monkeypatch.setattr(blocks_module, "actor_connection", fake_actor_connection)
    with pytest.raises(BlockRepositoryError) as raised:
        await PostgresBlockRepository().set(ACTOR, "st_owner", True)
    assert raised.value.code == "SELF_BLOCK_NOT_ALLOWED"
