"""Application settings that select infrastructure implementations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


RepositoryBackend = Literal["memory", "postgres"]


def reject_unsafe_in_production(name: str, enabled: bool, environment: str) -> None:
    """本番で認証や運用の安全装置を外す設定を、起動時に拒否する。

    黙って無効化せず起動を止める。設定した本人が気づけないまま
    公開されるのを防ぐためで、`REQUEST_REPOSITORY` と同じ扱いにしている。
    """
    if environment == "production" and enabled:
        raise RuntimeError(f"{name} must be disabled in production")


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

    if environment == "test":
        if configured_backend and backend != "memory":
            raise RuntimeError("REQUEST_REPOSITORY must be memory in test")
        backend = "memory"
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
