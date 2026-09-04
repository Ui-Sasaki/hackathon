"""本人確認申請と、安全な画像参照の受け渡しのテスト。"""

import asyncio
import os

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["REQUEST_REPOSITORY"] = "memory"

import httpx

import app.cruds.main as crud_module
from app.auth import CurrentUser, get_current_user
from app.main import app

from tests.test_uploads import (
    ASGITestClient, OTHER, OWNER, act_as, png_bytes,
)

client = ASGITestClient()

VERIFIER = CurrentUser(
    user_id="usr_verifier", role="verifier", status="active",
    email_verified=True, verification_status="approved", mfa_completed=True,
)
VERIFIER_WITHOUT_MFA = CurrentUser(
    user_id="usr_verifier", role="verifier", status="active",
    email_verified=True, verification_status="approved", mfa_completed=False,
)


def setup_function() -> None:
    act_as(OWNER)
    client.post("/_mock/reset")


def stored_upload(purpose: str = "verification_document") -> str:
    created = client.post(
        "/uploads",
        json={
            "purpose": purpose,
            "contentType": "image/png",
            "byteSize": 1024,
            "fileName": "card.png",
        },
    )
    assert created.status_code == 201, created.text
    upload = created.json()
    sent = client.put(
        upload["uploadUrl"],
        content=png_bytes(),
        headers={"Content-Type": "image/png"},
    )
    assert sent.status_code == 200, sent.text
    return upload["uploadId"]


def test_university_email_application_needs_no_image() -> None:
    response = client.post("/verifications", json={"method": "university_email"})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["userId"] == OWNER.user_id


def test_student_card_application_requires_an_upload() -> None:
    response = client.post("/verifications", json={"method": "student_card"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UPLOAD_REQUIRED"


def test_student_card_application_accepts_an_upload_reference() -> None:
    response = client.post(
        "/verifications",
        json={"method": "student_card", "uploadId": stored_upload()},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_application_never_returns_the_image_reference() -> None:
    body = client.post(
        "/verifications",
        json={"method": "student_card", "uploadId": stored_upload()},
    ).json()

    assert set(body) == {"id", "userId", "method", "status", "createdAt"}
    serialized = str(body)
    assert "private/" not in serialized
    assert "uploadId" not in serialized
    assert "imageId" not in serialized


def test_verification_document_is_not_reachable_through_the_profile_image_path() -> None:
    upload_id = stored_upload()
    application = client.post(
        "/verifications", json={"method": "student_card", "uploadId": upload_id}
    )
    assert application.status_code == 201

    repository = crud_module.get_upload_repository()
    session = asyncio.run(repository.get_session(upload_id))
    # 申請で確定済みのため、アップロードは再利用できない。
    assert session["status"] == "consumed"

    record = next(
        item for item in crud_module.verifications.values()
        if item["userId"] == OWNER.user_id
    )
    image = asyncio.run(repository.get_image(record["_imageId"]))
    # 参照子を知っていても、本人確認書類はプロフィール画像として配信されない。
    assert client.get(f"/profile/images/{image['viewToken']}").status_code == 404


def test_email_verified_and_verification_status_stay_separate() -> None:
    before = client.get("/profile").json()
    assert before["emailVerified"] is True

    client.post("/verifications", json={"method": "university_email"})
    after = client.get("/profile").json()

    assert after["verificationStatus"] == "pending"
    # 申請はメール確認状態を変えない。
    assert after["emailVerified"] == before["emailVerified"]


def test_a_second_application_while_pending_is_rejected() -> None:
    assert client.post("/verifications", json={"method": "university_email"}).status_code == 201

    response = client.post("/verifications", json={"method": "university_email"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERIFICATION_ALREADY_PENDING"


def test_a_rejected_duplicate_does_not_consume_the_upload() -> None:
    client.post("/verifications", json={"method": "university_email"})
    upload_id = stored_upload()

    assert client.post(
        "/verifications", json={"method": "student_card", "uploadId": upload_id}
    ).status_code == 409

    # 重複で弾かれたアップロードは、審査状態が戻れば使い直せる。
    session = asyncio.run(crud_module.get_upload_repository().get_session(upload_id))
    assert session["status"] == "stored"


def test_another_users_upload_cannot_be_submitted() -> None:
    upload_id = stored_upload()
    act_as(OTHER)

    response = client.post(
        "/verifications", json={"method": "student_card", "uploadId": upload_id}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UPLOAD_NOT_FOUND"


def test_a_profile_image_upload_cannot_be_submitted_as_a_document() -> None:
    response = client.post(
        "/verifications",
        json={"method": "student_card", "uploadId": stored_upload("profile_image")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UPLOAD_PURPOSE_MISMATCH"


def test_an_upload_without_content_cannot_be_submitted() -> None:
    created = client.post(
        "/uploads",
        json={
            "purpose": "verification_document",
            "contentType": "image/png",
            "byteSize": 1024,
        },
    )

    response = client.post(
        "/verifications",
        json={"method": "student_card", "uploadId": created.json()["uploadId"]},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "UPLOAD_CONTENT_MISSING"


def test_an_unknown_upload_is_not_found() -> None:
    response = client.post(
        "/verifications", json={"method": "student_card", "uploadId": "missing"}
    )

    assert response.status_code == 404


def test_application_requires_authentication() -> None:
    app.dependency_overrides.pop(get_current_user, None)

    assert client.post(
        "/verifications", json={"method": "university_email"}
    ).status_code == 401


def test_verifier_can_list_pending_requests_without_private_references() -> None:
    upload_id = stored_upload()
    created = client.post(
        "/verifications", json={"method": "student_card", "uploadId": upload_id}
    ).json()
    act_as(VERIFIER)

    response = client.get("/verification-reviews")

    assert response.status_code == 200
    assert response.json()["items"] == [{
        "id": created["id"], "userId": OWNER.user_id, "method": "student_card",
        "status": "pending", "createdAt": created["createdAt"],
        "reviewedAt": None, "deletionDueAt": None,
        "deletedAt": None, "hasDocument": True,
    }]
    assert "storageObjectKey" not in response.text
    assert "imageId" not in response.text


def test_only_mfa_completed_reviewer_can_access_review_api() -> None:
    client.post("/verifications", json={"method": "university_email"})

    act_as(OWNER)
    assert client.get("/verification-reviews").status_code == 403
    act_as(VERIFIER_WITHOUT_MFA)
    response = client.get("/verification-reviews")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MFA_REQUIRED"


def test_document_access_is_short_lived_scoped_and_audited() -> None:
    created = client.post(
        "/verifications", json={"method": "student_card", "uploadId": stored_upload()}
    ).json()
    act_as(VERIFIER)

    access = client.post(
        f"/verification-reviews/{created['id']}/document-access"
    )
    assert access.status_code == 200
    assert set(access.json()) == {"url", "expiresAt"}
    assert "private/" not in access.text

    viewed = client.get(access.json()["url"])
    assert viewed.status_code == 200
    assert viewed.headers["cache-control"] == "no-store"
    assert viewed.headers["content-type"] == "image/png"
    assert [event["eventType"] for event in crud_module.audit_logs[-2:]] == [
        "verification_document_access_granted", "verification_document_viewed",
    ]

    act_as(CurrentUser(
        user_id="other_verifier", role="verifier", status="active",
        email_verified=True, verification_status="approved", mfa_completed=True,
    ))
    assert client.get(access.json()["url"]).status_code == 404


def test_reviewer_decision_updates_user_and_rejects_second_decision() -> None:
    created = client.post(
        "/verifications", json={"method": "university_email"}
    ).json()
    act_as(VERIFIER)

    approved = client.post(
        f"/verification-reviews/{created['id']}/decision",
        json={"decision": "approved"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert "reviewerId" not in approved.json()
    assert crud_module.users_store[OWNER.user_id]["verificationStatus"] == "approved"
    assert crud_module.audit_logs[-1]["eventType"] == "verification_approved"

    conflict = client.post(
        f"/verification-reviews/{created['id']}/decision",
        json={"decision": "rejected"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "VERIFICATION_STATE_CONFLICT"


def test_reviewed_document_can_be_deleted_and_is_audited() -> None:
    created = client.post(
        "/verifications", json={"method": "student_card", "uploadId": stored_upload()}
    ).json()
    act_as(VERIFIER)
    client.post(
        f"/verification-reviews/{created['id']}/decision",
        json={"decision": "rejected"},
    )

    deleted = client.delete(f"/verification-reviews/{created['id']}/document")

    assert deleted.status_code == 200
    assert deleted.json()["hasDocument"] is False
    assert deleted.json()["deletedAt"] is not None
    assert crud_module.audit_logs[-1]["eventType"] == "verification_document_deleted"
