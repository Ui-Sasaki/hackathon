import logging
import os
import asyncio

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
# Local schema-identical Postgres (see supabase/tests/run.sh). trust auth, no
# secret involved. sslmode=disable avoids a crash in asyncpg's SSL-negotiation
# fallback path on native Windows Python when the server doesn't offer TLS.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://tetote_app@127.0.0.1:55432/tetote?sslmode=disable"
)

import httpx
from fastapi import HTTPException
from starlette.requests import Request

import app.auth as auth_module
from app.auth import CurrentUser, get_current_user
from app.cruds.main import SEED_REQUEST_1024
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
    role="member",
    status="active",
    email_verified=True,
    verification_status="approved",
)
HELPER = CurrentUser(
    user_id="usr_207",
    role="member",
    status="active",
    email_verified=True,
    verification_status="approved",
)


async def requester_user() -> CurrentUser:
    return REQUESTER


def setup_function() -> None:
    app.dependency_overrides[get_current_user] = requester_user
    client.post("/_mock/reset")


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
        json={"requestId": SEED_REQUEST_1024, "expectedVersion": 3},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "matched"

    conflict = client.post(
        "/applications/app_56/select",
        json={"requestId": SEED_REQUEST_1024, "expectedVersion": 3},
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
    async def helper_user() -> CurrentUser:
        return HELPER

    app.dependency_overrides[get_current_user] = helper_user
    response = client.post(
        f"/requests/{SEED_REQUEST_1024}/applications",
        json={"message": "対応できます", "availableAt": "2026-08-19T17:00:00+09:00"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_APPLICATION"


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
            "targetId": SEED_REQUEST_1024,
            "reason": "dangerous_work",
            "description": "高所で危険な作業を要求されています",
        },
    )
    assert response.status_code == 201
    assert client.get(f"/requests/{SEED_REQUEST_1024}").json()["status"] == "suspended"


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


def test_mock_reset_is_hidden_outside_enabled_environment(monkeypatch) -> None:
    async def unauthenticated() -> CurrentUser:
        raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED"})

    import app.cruds.main as cruds_main

    monkeypatch.setattr(cruds_main, "MOCK_RESET_ENABLED", False)
    app.dependency_overrides[get_current_user] = unauthenticated

    response = client.post("/_mock/reset")
    assert response.status_code == 404
    app.dependency_overrides[get_current_user] = requester_user
    assert client.get("/requests", params={"areaCode": "AREA-001"}).status_code == 200


def test_mock_reset_rejects_missing_session() -> None:
    async def unauthenticated() -> CurrentUser:
        raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED"})

    app.dependency_overrides[get_current_user] = unauthenticated
    response = client.post("/_mock/reset")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_mock_reset_succeeds_for_authenticated_caller_in_enabled_environment() -> None:
    response = client.post("/_mock/reset")
    assert response.status_code == 200
    assert response.json()["reset"] is True


def create_match() -> str:
    response = client.post(
        "/applications/app_55/select",
        json={"requestId": SEED_REQUEST_1024, "expectedVersion": 3},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_complete_match_needs_both_parties_and_tolerates_repeat() -> None:
    async def helper_user() -> CurrentUser:
        return HELPER

    match_id = create_match()
    first = client.post(
        f"/matches/{match_id}/complete",
        json={"completed": True, "actorRole": "requester"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "completion_pending"

    repeated = client.post(
        f"/matches/{match_id}/complete",
        json={"completed": True, "actorRole": "requester"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "completion_pending"

    app.dependency_overrides[get_current_user] = helper_user
    second = client.post(
        f"/matches/{match_id}/complete",
        json={"completed": True, "actorRole": "helper"},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "completed"


def test_complete_match_is_rejected_after_dispute() -> None:
    match_id = create_match()
    disputed = client.post(
        f"/matches/{match_id}/dispute",
        json={"reason": "作業内容の認識が食い違ったため確認したい"},
    )
    assert disputed.status_code == 200
    assert disputed.json()["status"] == "disputed"

    conflict = client.post(
        f"/matches/{match_id}/complete",
        json={"completed": True, "actorRole": "requester"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "MATCH_NOT_COMPLETABLE"

    match_after = client.get(f"/matches/{match_id}").json()
    assert match_after["status"] == "disputed"
    assert match_after["requesterConfirmed"] is False
    assert match_after["completedAt"] is None
    assert client.get(f"/requests/{SEED_REQUEST_1024}").json()["status"] == "disputed"


def test_complete_match_is_rejected_after_completion() -> None:
    async def helper_user() -> CurrentUser:
        return HELPER

    match_id = create_match()
    client.post(
        f"/matches/{match_id}/complete",
        json={"completed": True, "actorRole": "requester"},
    )
    app.dependency_overrides[get_current_user] = helper_user
    completed = client.post(
        f"/matches/{match_id}/complete",
        json={"completed": True, "actorRole": "helper"},
    )
    assert completed.json()["status"] == "completed"

    conflict = client.post(
        f"/matches/{match_id}/complete",
        json={"completed": True, "actorRole": "helper"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "MATCH_NOT_COMPLETABLE"


def test_seeded_profile_uses_member_role() -> None:
    response = client.get("/profile")
    assert response.status_code == 200
    assert response.json()["role"] == "member"


def test_require_roles_accepts_member(monkeypatch) -> None:
    async def as_member(_request) -> CurrentUser:
        return CurrentUser(
            user_id="usr_101",
            role="member",
            status="active",
            email_verified=True,
            verification_status="approved",
        )

    monkeypatch.setattr(auth_module, "get_current_user", as_member)
    user = asyncio.run(auth_module.require_roles("member")(None))
    assert user.role == "member"


def test_require_roles_rejects_unlisted_role(monkeypatch) -> None:
    async def as_member(_request) -> CurrentUser:
        return CurrentUser(
            user_id="usr_101",
            role="member",
            status="active",
            email_verified=True,
            verification_status="approved",
        )

    monkeypatch.setattr(auth_module, "get_current_user", as_member)
    try:
        asyncio.run(auth_module.require_roles("admin")(None))
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail["code"] == "ROLE_FORBIDDEN"
    else:
        raise AssertionError("member must not pass an admin-only dependency")


def test_privileged_roles_still_require_mfa(monkeypatch) -> None:
    for privileged in ("admin", "verifier"):

        async def as_privileged(_request, role: str = privileged) -> CurrentUser:
            return CurrentUser(
                user_id="usr_900",
                role=role,
                status="active",
                email_verified=True,
                verification_status="approved",
                mfa_completed=False,
            )

        monkeypatch.setattr(auth_module, "get_current_user", as_privileged)
        try:
            asyncio.run(auth_module.require_roles(privileged)(None))
        except HTTPException as exc:
            assert exc.status_code == 403
            assert exc.detail["code"] == "MFA_REQUIRED"
        else:
            raise AssertionError(f"{privileged} must require MFA")
