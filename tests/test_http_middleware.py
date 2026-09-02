import pytest

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
