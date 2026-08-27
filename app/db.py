"""Postgres connections and per-request actor context.

Runtime connects as `tetote_app` (NOBYPASSRLS). RLS policies read the current
actor from a transaction-local setting, so every authenticated request must:

1. resolve (or provision) the internal `users.id` for the SuperTokens subject
   via the `app.ensure_user` SECURITY DEFINER function, which is the only
   permitted way to create a `users` row (see supabase/migrations/
   20260821000000_user_provisioning.sql);
2. set `app.actor_id` for that transaction via `set_config(..., true)`
   (transaction-local — never session-level, so it cannot leak across a
   pooled/reused connection);
3. run the endpoint's queries inside that same transaction;
4. commit or roll back, then close the connection.

`actor_connection()` implements exactly this sequence and is the only
supported way application code should reach the database.

This opens a fresh connection per call rather than pooling. The test harness
(`tests/main.py`'s `ASGITestClient`) runs every request through its own
`asyncio.run()`, i.e. a new event loop each time — an `asyncpg.Pool` created
on one loop cannot be reused from another, so a shared pool would break on
the second request. Per-request connections sidestep that entirely and are
adequate for this app's scale; revisit pooling only if connection setup cost
is measured to matter.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.auth import CurrentUser
from app.settings import settings


def _database_url() -> str:
    url = settings.database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Point it at a Postgres instance that has "
            "supabase/migrations applied (see supabase/tests/run.sh for a local one)."
        )
    return url


@asynccontextmanager
async def actor_connection(current_user: CurrentUser) -> AsyncIterator[asyncpg.Connection]:
    # statement_cache_size=0: Supabase's transaction-mode pooler does not
    # support prepared statements. Harmless for direct/session connections.
    conn = await asyncpg.connect(_database_url(), statement_cache_size=0)
    try:
        async with conn.transaction():
            actor_id = await conn.fetchval(
                "select app.ensure_user($1, $2, $3::account_role)",
                current_user.user_id,
                # Profile management (display_name) is out of scope for #4;
                # the SuperTokens subject is used as a placeholder until a
                # real profile endpoint provisions one.
                current_user.user_id,
                current_user.role,
            )
            await conn.execute("select set_config('app.actor_id', $1, true)", str(actor_id))
            yield conn
    finally:
        await conn.close()


@asynccontextmanager
async def admin_connection() -> AsyncIterator[asyncpg.Connection]:
    """A connection with no actor context set.

    Only usable for narrow SECURITY DEFINER functions that establish identity
    or read non-personal master data, plus the `/_mock/reset` test-support path.
    Ordinary business queries must go through `actor_connection`, which RLS
    depends on.
    """
    # statement_cache_size=0: Supabase's transaction-mode pooler does not
    # support prepared statements. Harmless for direct/session connections.
    conn = await asyncpg.connect(_database_url(), statement_cache_size=0)
    try:
        async with conn.transaction():
            yield conn
    finally:
        await conn.close()
