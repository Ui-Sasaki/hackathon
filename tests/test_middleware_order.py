"""ミドルウェアの重なり順のテスト。

Starlette は後から add_middleware したものが外側になる。CORS が SuperTokens より
内側にあると、SuperTokens が /auth/* に直接返す応答に Access-Control-Allow-Origin
が付かず、フロントとAPIのドメインが異なる本番で新規登録・ログインが失敗する。
"""

import asyncio
import os

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["REQUEST_REPOSITORY"] = "memory"
os.environ["WEBSITE_DOMAIN"] = "https://front.example.test"

import httpx
from starlette.middleware.cors import CORSMiddleware

from app.main import app

def middleware_names() -> list[str]:
    # user_middleware は先頭が最も外側。
    return [middleware.cls.__name__ for middleware in app.user_middleware]


def allowed_origin() -> str:
    """app が実際に許可している画面のオリジン。

    他のテストが先に app を読み込むと WEBSITE_DOMAIN の既定値で固定されるため、
    環境変数ではなく登録済みの CORS 設定から取る。
    """
    for middleware in app.user_middleware:
        if middleware.cls is CORSMiddleware:
            options = getattr(middleware, "kwargs", None) or getattr(middleware, "options", {})
            return options["allow_origins"][0]
    raise AssertionError("CORSMiddleware が登録されていない")


ORIGIN = allowed_origin()


def test_cors_is_outside_the_auth_and_prefix_middlewares() -> None:
    names = middleware_names()
    cors_index = names.index("CORSMiddleware")
    prefix_index = names.index("ApiPrefixMiddleware")
    # SuperTokens は ApiPrefixMiddleware の直後に登録されるので、CORS が
    # ApiPrefixMiddleware より外側なら SuperTokens より外側でもある。
    assert cors_index < prefix_index, names
    assert "Middleware" in names[cors_index]
    assert any(m.cls is CORSMiddleware for m in app.user_middleware)


def send(method: str, path: str, **kwargs) -> httpx.Response:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(run())


def test_cors_headers_are_added_to_responses_from_the_site_origin() -> None:
    preflight = send(
        "OPTIONS", "/health",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    actual = send("GET", "/health", headers={"Origin": ORIGIN})

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == ORIGIN
    assert actual.status_code == 200
    assert actual.headers["access-control-allow-origin"] == ORIGIN
    assert actual.headers["access-control-allow-credentials"] == "true"


def test_other_origins_get_no_cors_headers() -> None:
    response = send("GET", "/health", headers={"Origin": "https://evil.example.test"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
