"""HTTP middleware configuration shared by local and deployed environments."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def website_origin() -> str:
    """Return the configured frontend origin in canonical form."""

    origin = os.getenv("WEBSITE_DOMAIN", "http://localhost:3000").strip().rstrip("/")
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("WEBSITE_DOMAIN must be an http(s) origin without a path")
    return origin


def add_cors_middleware(app: FastAPI, *, allow_headers: list[str]) -> None:
    """Allow credentialed browser requests only from the configured frontend."""

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[website_origin()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=allow_headers,
    )
