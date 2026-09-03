import pytest
from fastapi.middleware.cors import CORSMiddleware

from app.auth import auth_cookie_same_site
from app.cruds.main import app
from app.http_middleware import website_origin


def test_website_origin_normalizes_whitespace_and_trailing_slash(monkeypatch) -> None:
    monkeypatch.setenv(
        "WEBSITE_DOMAIN", "  https://hackathon-tau-mauve.vercel.app/  "
    )

    assert website_origin() == "https://hackathon-tau-mauve.vercel.app"


@pytest.mark.parametrize(
    "value",
    [
        "hackathon-tau-mauve.vercel.app",
        "https://hackathon-tau-mauve.vercel.app/path",
        "https://hackathon-tau-mauve.vercel.app?preview=true",
    ],
)
def test_website_origin_rejects_non_origin_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("WEBSITE_DOMAIN", value)

    with pytest.raises(RuntimeError, match="WEBSITE_DOMAIN"):
        website_origin()


def test_cors_wraps_authentication_middleware() -> None:
    assert app.user_middleware[0].cls is CORSMiddleware


def test_cookie_same_site_defaults_to_none_for_cross_site_secure_deploy(
    monkeypatch,
) -> None:
    monkeypatch.delenv("AUTH_COOKIE_SAME_SITE", raising=False)
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("API_DOMAIN", "https://tetote-api.vercel.app")
    monkeypatch.setenv("WEBSITE_DOMAIN", "https://hackathon-tau-mauve.vercel.app")

    assert auth_cookie_same_site() == "none"


def test_cookie_same_site_defaults_to_lax_for_same_origin(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_COOKIE_SAME_SITE", raising=False)
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("API_DOMAIN", "https://tetote.example.com")
    monkeypatch.setenv("WEBSITE_DOMAIN", "https://tetote.example.com")

    assert auth_cookie_same_site() == "lax"


def test_cookie_same_site_explicit_value_wins(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_COOKIE_SAME_SITE", "strict")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("API_DOMAIN", "https://tetote-api.vercel.app")
    monkeypatch.setenv("WEBSITE_DOMAIN", "https://hackathon-tau-mauve.vercel.app")

    assert auth_cookie_same_site() == "strict"
