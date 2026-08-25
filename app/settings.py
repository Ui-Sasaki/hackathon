"""Application settings that select infrastructure implementations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


RepositoryBackend = Literal["memory", "postgres"]


@dataclass(frozen=True)
class Settings:
    environment: str
    request_repository: RepositoryBackend
    database_url: str | None


def load_settings() -> Settings:
    """Load repository selection once, with a fail-closed production mode."""

    environment = os.getenv("APP_ENV", "development").lower()
    configured_backend = os.getenv("REQUEST_REPOSITORY")
    backend = configured_backend.lower() if configured_backend else "memory"

    if environment == "production":
        if configured_backend and backend != "postgres":
            raise RuntimeError("REQUEST_REPOSITORY must be postgres in production")
        backend = "postgres"
    if backend not in {"memory", "postgres"}:
        raise RuntimeError("REQUEST_REPOSITORY must be memory or postgres")

    database_url = os.getenv("DATABASE_URL")
    if backend == "postgres" and not database_url:
        raise RuntimeError("DATABASE_URL is required for the Postgres repository")

    return Settings(
        environment=environment,
        request_repository=backend,
        database_url=database_url,
    )


settings = load_settings()
