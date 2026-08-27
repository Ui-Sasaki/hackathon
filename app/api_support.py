"""Shared FastAPI dependencies and OpenAPI error contracts."""

from typing import Any

from app.repositories.applications import (
    ApplicationRepository,
    get_application_repository,
)
from app.repositories.matches import MatchRepository, get_match_repository
from app.repositories.requests import RequestRepository, get_request_repository
from app.schemas import ErrorResponse


def api_errors(*statuses: int) -> dict[int, dict[str, Any]]:
    """Return the error contracts reachable by an API operation."""

    examples = {
        400: ("BAD_REQUEST", "リクエストを処理できません"),
        401: ("AUTHENTICATION_REQUIRED", "認証が必要です"),
        403: ("ROLE_FORBIDDEN", "この操作を行う権限がありません"),
        404: ("REQUEST_NOT_FOUND", "対象が見つかりません"),
        409: (
            "REQUEST_STATE_CONFLICT",
            "依頼の状態が更新されているため処理できません",
        ),
        422: ("VALIDATION_ERROR", "入力内容を確認してください"),
        500: ("INTERNAL_SERVER_ERROR", "サーバー内部でエラーが発生しました"),
    }
    return {
        status: {
            "model": ErrorResponse,
            "description": examples[status][1],
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": examples[status][0],
                            "message": examples[status][1],
                            "details": {},
                            "requestId": "trace_0123abcd",
                        }
                    }
                }
            },
        }
        for status in statuses
    }


async def request_repository_dependency() -> RequestRepository:
    """Resolve the configured request repository without a threadpool hop."""

    return get_request_repository()


async def application_repository_dependency() -> ApplicationRepository:
    """Resolve the configured application repository without a threadpool hop."""

    return get_application_repository()


async def match_repository_dependency() -> MatchRepository:
    """Resolve the configured matching repository without a threadpool hop."""

    return get_match_repository()
