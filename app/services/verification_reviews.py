"""本人確認審査の認可と状態遷移。"""

from __future__ import annotations

from fastapi import HTTPException

from app.auth import CurrentUser
from app.repositories.uploads import UploadRepository
from app.repositories.verification_reviews import (
    ReviewDecision, VerificationReviewRepository,
    VerificationReviewRepositoryError,
)


def _raise_repository_error(exc: VerificationReviewRepositoryError) -> None:
    status = 404 if exc.code in {
        "VERIFICATION_NOT_FOUND", "VERIFICATION_DOCUMENT_NOT_FOUND"
    } else 409
    raise HTTPException(status, detail={"code": exc.code}) from exc


async def decide(
    repository: VerificationReviewRepository,
    verification_id: str,
    reviewer: CurrentUser,
    decision: ReviewDecision,
) -> dict:
    try:
        return await repository.decide(verification_id, reviewer, decision)
    except VerificationReviewRepositoryError as exc:
        _raise_repository_error(exc)


async def delete_document(
    repository: VerificationReviewRepository,
    uploads: UploadRepository,
    verification_id: str,
    actor: CurrentUser,
) -> dict:
    item = await repository.get(verification_id)
    if item is None:
        raise HTTPException(404, detail={"code": "VERIFICATION_NOT_FOUND"})
    image_id = item.get("_imageId")
    if not image_id:
        raise HTTPException(404, detail={"code": "VERIFICATION_DOCUMENT_NOT_FOUND"})
    if item["status"] == "pending":
        raise HTTPException(409, detail={"code": "VERIFICATION_STATE_CONFLICT"})
    if not await uploads.delete_image(image_id):
        raise HTTPException(404, detail={"code": "VERIFICATION_DOCUMENT_NOT_FOUND"})
    try:
        return await repository.mark_document_deleted(verification_id, actor)
    except VerificationReviewRepositoryError as exc:
        _raise_repository_error(exc)
