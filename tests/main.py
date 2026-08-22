import logging
import os
import asyncio

os.environ["SUPERTOKENS_ENABLED"] = "false"

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.auth as auth_module
import app.cruds.main as crud_module
from app.auth import CurrentUser, get_current_user
from app.main import app


class ASGITestClient:
    """Small synchronous wrapper that keeps tests independent of a live server."""

    def __init__(self, raise_server_exceptions: bool = True) -> None:
        self.raise_server_exceptions = raise_server_exceptions

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(
                app=app, raise_app_exceptions=self.raise_server_exceptions
            )
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as async_client:
                return await async_client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)


client = ASGITestClient()


@app.get("/_test/unhandled", include_in_schema=False)
async def raise_unhandled_error() -> None:
    raise RuntimeError("private database failure: user@example.com")


@app.get("/_test/http-error/{status_code}", include_in_schema=False)
async def raise_http_error(status_code: int) -> None:
    raise HTTPException(status_code, detail="private framework detail")


REQUESTER = CurrentUser(
    user_id="usr_101",
    role="requester",
    status="active",
    email_verified=True,
    verification_status="approved",
)
HELPER = CurrentUser(
    user_id="usr_207",
    role="helper",
    status="active",
    email_verified=True,
    verification_status="approved",
)


async def requester_user() -> CurrentUser:
    return REQUESTER


def setup_function() -> None:
    app.dependency_overrides[get_current_user] = requester_user
    client.post("/_mock/reset")
    crud_module.configure_achievement_generator(crud_module.default_achievement_generator)


def seed_completed_match() -> dict:
    match = {
        "id": "match_completed",
        "requestId": "req_1024",
        "requesterId": "usr_101",
        "helperId": "usr_207",
        "status": "completed",
        "requesterConfirmed": True,
        "helperConfirmed": True,
        "matchedAt": "2026-08-19T17:00:00+09:00",
        "completedAt": "2026-08-19T17:30:00+09:00",
    }
    crud_module.matches[match["id"]] = match
    crud_module.requests_store["req_1024"]["status"] = "completed"
    return match


async def helper_user() -> CurrentUser:
    return HELPER


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_requests() -> None:
    response = client.get("/requests", params={"areaCode": "AREA-001"})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def test_structure_request() -> None:
    response = client.post(
        "/requests/structure",
        json={"text": "病気なので犬の散歩をお願いしたい", "areaCode": "AREA-001"},
    )
    assert response.status_code == 200
    assert response.json()["category"] == "pet_support"


def test_select_application_with_version_check() -> None:
    response = client.post(
        "/applications/app_55/select",
        json={"requestId": "req_1024", "expectedVersion": 3},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "matched"

    conflict = client.post(
        "/applications/app_56/select",
        json={"requestId": "req_1024", "expectedVersion": 3},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "REQUEST_STATE_CONFLICT"


def test_api_prefix_and_profile_update() -> None:
    response = client.patch("/api/profile", json={"displayName": "更新後の名前"})
    assert response.status_code == 200
    assert response.json()["displayName"] == "更新後の名前"


def test_create_request_is_idempotent() -> None:
    payload = {
        "title": "庭の片付け",
        "description": "庭の落ち葉を一緒に片付けてください",
        "category": "cleaning",
        "scheduledAt": "2026-08-22T10:00:00+09:00",
        "estimatedMinutes": 30,
        "requiredHelpers": 1,
        "areaCode": "AREA-001",
        "riskLevel": "low",
        "confirmed": True,
    }
    headers = {"Idempotency-Key": "same-operation"}
    first = client.post("/api/requests", json=payload, headers=headers)
    second = client.post("/api/requests", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


def test_duplicate_application_is_rejected() -> None:
    app.dependency_overrides[get_current_user] = helper_user
    response = client.post(
        "/requests/req_1024/applications",
        json={"message": "対応できます", "availableAt": "2026-08-19T17:00:00+09:00"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_APPLICATION"


def test_review_requires_completed_match_and_is_unique_per_reviewer() -> None:
    match = seed_completed_match()
    payload = {
        "onTime": True,
        "polite": True,
        "safetyAware": True,
        "communicative": True,
        "comment": "安全に配慮して丁寧に対応してくれました",
    }

    match["status"] = "completion_pending"
    incomplete = client.post(f"/matches/{match['id']}/reviews", json=payload)
    match["status"] = "completed"
    first = client.post(f"/matches/{match['id']}/reviews", json=payload)
    duplicate = client.post(f"/matches/{match['id']}/reviews", json=payload)

    assert incomplete.status_code == 409
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_REVIEW"


@pytest.mark.parametrize(
    "comment",
    [
        "連絡先はhanako@example.comです",
        "電話番号は090-1234-5678です",
        "糖尿病のことを皆に伝えます",
        "本当にクズな対応でした",
    ],
)
def test_review_rejects_personal_or_abusive_content(comment: str) -> None:
    match = seed_completed_match()
    response = client.post(
        f"/matches/{match['id']}/reviews",
        json={
            "onTime": False,
            "polite": False,
            "safetyAware": False,
            "communicative": False,
            "comment": comment,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REVIEW_CONTENT_REJECTED"


def test_achievement_aggregates_completed_activity_and_masks_llm_input() -> None:
    match = seed_completed_match()
    crud_module.requests_store["req_1024"]["description"] = (
        "山田 花子さん（糖尿病）の連絡先は090-1234-5678です"
    )
    captured_payload = {}

    async def generator(payload: dict) -> dict:
        captured_payload.update(payload)
        return {
            "activitySummary": "山田 花子さんを支援しました",
            "strengths": ["山田 花子さんへの丁寧な対応"],
            "generatedText": "山田 花子さんの依頼を完了しました",
        }

    crud_module.configure_achievement_generator(generator)
    app.dependency_overrides[get_current_user] = helper_user
    response = client.post(
        "/achievements/generate",
        json={"matchId": match["id"], "visibility": "private"},
    )

    assert response.status_code == 201
    achievement = response.json()
    assert achievement["facts"] == {
        "totalActivities": 1,
        "totalMinutes": 30,
        "categoryCounts": {"pet_support": 1},
    }
    assert achievement["visibility"] == "private"
    assert achievement["approvedAt"] is None
    assert achievement["aiGenerated"] is True
    assert achievement["modelName"] == "mock-achievement-model"
    assert achievement["promptVersion"] == "achievement-v1"
    assert "AI" in achievement["generatedText"]
    serialized_input = str(captured_payload)
    serialized_output = str(achievement)
    for private_value in ("山田 花子", "糖尿病", "090-1234-5678"):
        assert private_value not in serialized_input
        assert private_value not in serialized_output


def test_achievement_generation_requires_helper_and_completed_match() -> None:
    match = seed_completed_match()
    requester_response = client.post(
        "/achievements/generate",
        json={"matchId": match["id"], "visibility": "private"},
    )
    assert requester_response.status_code == 403

    app.dependency_overrides[get_current_user] = helper_user
    match["status"] = "completion_pending"
    incomplete_response = client.post(
        "/achievements/generate",
        json={"matchId": match["id"], "visibility": "private"},
    )
    assert incomplete_response.status_code == 409


def test_achievement_can_be_regenerated_and_visibility_is_owner_controlled() -> None:
    match = seed_completed_match()
    app.dependency_overrides[get_current_user] = helper_user
    first = client.post(
        "/achievements/generate",
        json={"matchId": match["id"], "visibility": "private"},
    )
    second = client.post(
        "/achievements/generate",
        json={"matchId": match["id"], "visibility": "private"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    app.dependency_overrides[get_current_user] = requester_user
    forbidden = client.patch(
        "/achievements/visibility",
        json={"achievementId": second.json()["id"], "visibility": "private"},
    )
    app.dependency_overrides[get_current_user] = helper_user
    unapproved = client.patch(
        "/achievements/visibility",
        json={"achievementId": second.json()["id"], "visibility": "public"},
    )
    unapproved_members = client.patch(
        "/achievements/visibility",
        json={"achievementId": second.json()["id"], "visibility": "members"},
    )
    approved = client.patch(
        "/achievements/visibility",
        json={
            "achievementId": second.json()["id"],
            "visibility": "public",
            "approved": True,
        },
    )
    private = client.patch(
        "/achievements/visibility",
        json={"achievementId": second.json()["id"], "visibility": "private"},
    )
    assert forbidden.status_code == 403
    assert unapproved.status_code == 409
    assert unapproved_members.status_code == 409
    assert approved.json()["status"] == "approved"
    assert approved.json()["approvedAt"] is not None
    assert private.json()["visibility"] == "private"
    assert private.json()["status"] == "private"


def test_generation_failure_preserves_existing_public_achievement() -> None:
    match = seed_completed_match()
    existing = {
        "id": "ach_public",
        "userId": "usr_207",
        "visibility": "public",
        "status": "approved",
        "generatedText": "既存の公開実績",
    }
    crud_module.achievements[existing["id"]] = existing.copy()

    async def unavailable(_payload: dict) -> dict:
        raise TimeoutError("secret provider failure")

    crud_module.configure_achievement_generator(unavailable)
    app.dependency_overrides[get_current_user] = helper_user
    response = client.post(
        "/achievements/generate",
        json={"matchId": match["id"], "visibility": "private"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ACHIEVEMENT_GENERATION_UNAVAILABLE"
    assert crud_module.achievements == {existing["id"]: existing}


def test_protected_endpoint_rejects_missing_session() -> None:
    async def unauthenticated() -> CurrentUser:
        from fastapi import HTTPException

        raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED"})

    app.dependency_overrides[get_current_user] = unauthenticated
    response = client.get("/profile")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_requester_id_comes_from_verified_session() -> None:
    payload = {
        "title": "庭の片付け",
        "description": "庭の落ち葉を一緒に片付けてください",
        "category": "cleaning",
        "scheduledAt": "2026-08-22T10:00:00+09:00",
        "estimatedMinutes": 30,
        "requiredHelpers": 1,
        "areaCode": "AREA-001",
        "riskLevel": "low",
        "confirmed": True,
        "requesterId": "attacker-controlled",
    }
    response = client.post(
        "/requests", json=payload, headers={"Idempotency-Key": "identity-test"}
    )
    assert response.status_code == 201
    assert response.json()["requesterId"] == "usr_101"


def test_session_dependency_returns_verified_user(monkeypatch) -> None:
    class FakeSession:
        def get_user_id(self) -> str:
            return "usr_101"

        def get_access_token_payload(self) -> dict:
            return {}

    def fake_verify_session(**options):
        assert options == {"anti_csrf_check": True, "check_database": True}

        async def verify(_request):
            return FakeSession()

        return verify

    monkeypatch.setattr(auth_module, "SUPERTOKENS_ENABLED", True)
    monkeypatch.setattr(auth_module, "verify_session", fake_verify_session, raising=False)
    request = Request({"type": "http", "method": "GET", "path": "/profile", "headers": []})
    user = asyncio.run(get_current_user(request))
    assert user.user_id == "usr_101"
    assert user.verification_status == "approved"


def test_auth_mock_returns_default_user_without_session(monkeypatch) -> None:
    monkeypatch.setattr(auth_module, "AUTH_MOCK_ENABLED", True)
    monkeypatch.setattr(auth_module, "AUTH_MOCK_USER_ID", "usr_101")
    request = Request({"type": "http", "method": "GET", "path": "/profile", "headers": []})

    user = asyncio.run(get_current_user(request))

    assert user.user_id == "usr_101"
    assert user.role == "requester"
    assert user.mfa_completed is True


def test_auth_mock_can_select_existing_user_by_header(monkeypatch) -> None:
    monkeypatch.setattr(auth_module, "AUTH_MOCK_ENABLED", True)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/profile",
            "headers": [(b"x-mock-user-id", b"usr_207")],
        }
    )

    user = asyncio.run(get_current_user(request))

    assert user.user_id == "usr_207"
    assert user.role == "helper"


def test_auth_mock_rejects_unknown_user(monkeypatch) -> None:
    monkeypatch.setattr(auth_module, "AUTH_MOCK_ENABLED", True)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/profile",
            "headers": [(b"x-mock-user-id", b"unknown")],
        }
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_user(request))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == {"code": "USER_PROFILE_NOT_FOUND"}


def test_signup_profile_is_created_with_safe_defaults() -> None:
    crud_module.create_user_profile("supertokens-user-id")

    assert crud_module.users_store["supertokens-user-id"] == {
        "id": "supertokens-user-id",
        "displayName": "",
        "role": "requester",
        "status": "active",
        "emailVerified": False,
        "verificationStatus": "unverified",
    }


def test_signup_profile_creation_is_idempotent() -> None:
    crud_module.create_user_profile("usr_101")

    assert crud_module.users_store["usr_101"]["displayName"] == "山田 花子"
    assert crud_module.users_store["usr_101"]["verificationStatus"] == "approved"


def test_successful_signup_triggers_profile_creation(monkeypatch) -> None:
    created_user_ids: list[str] = []

    class FakeSignUpPostOkResult:
        user = type("User", (), {"id": "new-user-id"})()

    class FakeApis:
        async def sign_up_post(self, *_args, **_kwargs):
            return FakeSignUpPostOkResult()

        async def password_reset_post(self, *_args, **_kwargs):
            return object()

    monkeypatch.setattr(
        auth_module, "SignUpPostOkResult", FakeSignUpPostOkResult, raising=False
    )
    monkeypatch.setattr(auth_module, "_user_creator", created_user_ids.append)
    overridden = auth_module._override_emailpassword_apis(FakeApis())

    asyncio.run(overridden.sign_up_post())

    assert created_user_ids == ["new-user-id"]


def test_invalid_session_is_unauthorized(monkeypatch) -> None:
    def fake_verify_session(**_options):
        async def verify(_request):
            return None

        return verify

    monkeypatch.setattr(auth_module, "SUPERTOKENS_ENABLED", True)
    monkeypatch.setattr(auth_module, "verify_session", fake_verify_session, raising=False)
    request = Request({"type": "http", "method": "GET", "path": "/profile", "headers": []})
    try:
        asyncio.run(get_current_user(request))
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail["code"] == "AUTHENTICATION_REQUIRED"
    else:
        raise AssertionError("invalid session must be rejected")


def test_high_severity_report_suspends_request() -> None:
    response = client.post(
        "/reports",
        json={
            "targetType": "request",
            "targetId": "req_1024",
            "reason": "dangerous_work",
            "description": "高所で危険な作業を要求されています",
        },
    )
    assert response.status_code == 201
    assert client.get("/requests/req_1024").json()["status"] == "suspended"


def assert_common_error(response, status_code: int) -> dict:
    assert response.status_code == status_code
    error = response.json()["error"]
    assert set(error) == {"code", "message", "details", "requestId"}
    assert error["requestId"].startswith("trace_")
    assert response.headers["X-Request-ID"] == error["requestId"]
    return error


def test_not_found_uses_common_error_response() -> None:
    error = assert_common_error(client.get("/missing-endpoint"), 404)
    assert error["code"] == "NOT_FOUND"


def test_400_401_403_and_409_use_common_error_response() -> None:
    expected_codes = {
        400: "BAD_REQUEST",
        401: "AUTHENTICATION_REQUIRED",
        403: "ROLE_FORBIDDEN",
        409: "STATE_CONFLICT",
    }
    for status_code, expected_code in expected_codes.items():
        response = client.get(f"/_test/http-error/{status_code}")
        error = assert_common_error(response, status_code)
        assert error["code"] == expected_code
        assert "private framework detail" not in response.text


def test_validation_error_does_not_echo_private_input() -> None:
    private_value = "secret-personal-description"
    response = client.post(
        "/requests/structure",
        json={"text": private_value},
    )
    error = assert_common_error(response, 422)
    assert error["code"] == "VALIDATION_ERROR"
    assert private_value not in response.text


def test_unhandled_error_is_sanitized_and_correlated_with_log(caplog) -> None:
    with caplog.at_level(logging.ERROR, logger="app.cruds.main"):
        response = ASGITestClient(raise_server_exceptions=False).get("/_test/unhandled")

    error = assert_common_error(response, 500)
    assert error["code"] == "INTERNAL_SERVER_ERROR"
    assert "private database failure" not in response.text
    assert "user@example.com" not in response.text
    assert error["requestId"] in caplog.text
