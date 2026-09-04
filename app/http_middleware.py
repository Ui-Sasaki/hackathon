"""HTTP origin configuration shared by local and deployed environments."""

from __future__ import annotations

import os
from urllib.parse import urlsplit


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
