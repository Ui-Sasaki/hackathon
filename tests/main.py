import logging
import os
import asyncio
from copy import deepcopy

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
RECOMMENDER = CurrentUser(
    user_id="usr_209",
    role="helper",
    status="active",
    email_verified=True,
    verification_status="approved",
)


async def requester_user() -> CurrentUser:
    return REQUESTER


async def recommender_user() -> CurrentUser:
    return RECOMMENDER


def configure_recommender(*, verified: bool = True, with_history: bool = True) -> None:
    app.dependency_overrides[get_current_user] = recommender_user
    crud_module.users_store["usr_209"] = {
        "id": "usr_209",
        "displayName": "推薦利用者",
        "role": "helper",
        "status": "active",
        "emailVerified": True,
        "verificationStatus": "approved" if verified else "unverified",
        "areaCode": "AREA-001",
        "skillTags": ["犬"] if with_history else [],
        "preferredCategories": ["pet_support"] if with_history else [],
        "availableTimes": ["2026-08-25T10:00:00+09:00"] if with_history else [],
        "maxDistanceKm": 10,
        "categoryAchievements": {"pet_support": 5} if with_history else {},
    }


def add_recommendation_request(request_id: str, **overrides) -> dict:
    item = deepcopy(crud_module.INITIAL_REQUESTS[1])
    item.update(
        {
            "id": request_id,
            "requesterId": f"owner_{request_id}",
            "scheduledAt": "2026-08-25T10:00:00+09:00",
            "createdAt": "2026-08-22T10:00:00+09:00",
            "status": "published",
            "acceptedHelpers": 0,
        }
    )
    item.update(overrides)
    crud_module.requests_store[request_id] = item
    return item


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


def test_recommendations_rank_matches_and_explain_score_without_private_data() -> None:
    configure_recommender()
    add_recommendation_request(
        "req_best",
        category="pet_support",
        requiredSkills=["犬"],
        distanceKm=1.0,
        description="東京都新宿区1-2-3の山田さんを支援",
        approximateLatitude=35.123456,
        approximateLongitude=139.123456,
    )
    add_recommendation_request(
        "req_lower",
        category="cleaning",
        requiredSkills=["掃除"],
        distanceKm=8.0,
    )

    response = client.get("/requests/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == "req_best"
    assert body["items"][0]["recommendationScore"] > body["items"][1]["recommendationScore"]
    assert "希望カテゴリと一致" in body["items"][0]["recommendationReasons"]
    assert "スキル一致: 犬" in body["items"][0]["recommendationReasons"]
    assert body["scoringWeights"] == crud_module.RECOMMENDATION_WEIGHTS
    assert "再検証" in body["applicationPolicy"]
    serialized = str(body)
    for private_field in (
        "description",
        "requesterId",
        "approximateLatitude",
        "approximateLongitude",
        "35.123456",
        "139.123456",
    ):
        assert private_field not in serialized


def test_recommendations_exclude_ineligible_requests() -> None:
    configure_recommender(verified=False)
    own = add_recommendation_request("req_own", requesterId="usr_209")
    closed = add_recommendation_request("req_closed", status="matched")
    expired = add_recommendation_request(
        "req_expired", expiresAt="2026-08-21T00:00:00Z"
    )
    blocked = add_recommendation_request("req_blocked", requesterId="usr_blocked")
    verification = add_recommendation_request(
        "req_verified_only", verificationRequired=True
    )
    full = add_recommendation_request("req_full", requiredHelpers=1, acceptedHelpers=1)
    crud_module.blocks.add("usr_blocked")

    response = client.get("/requests/recommendations")

    assert response.status_code == 200
    returned_ids = {item["id"] for item in response.json()["items"]}
    excluded = {item["id"] for item in (own, closed, expired, blocked, verification, full)}
    assert returned_ids.isdisjoint(excluded)


def test_recommendations_use_cold_start_fallback_and_cursor_paging() -> None:
    configure_recommender(with_history=False)
    add_recommendation_request("req_cold_1", areaCode="AREA-001", distanceKm=1.0)
    add_recommendation_request("req_cold_2", areaCode="AREA-002", distanceKm=2.0)

    first = client.get("/requests/recommendations", params={"limit": 1})
    second = client.get(
        "/requests/recommendations",
        params={"limit": 1, "cursor": first.json()["nextCursor"]},
    )

    assert first.status_code == 200
    assert first.json()["nextCursor"] is not None
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]
    assert first.json()["items"][0]["recommendationReasons"]
    assert client.get("/requests/recommendations", params={"limit": 51}).status_code == 422
    assert client.get(
        "/requests/recommendations", params={"cursor": "not-a-cursor"}
    ).status_code == 422


def test_recommendations_require_authentication() -> None:
    async def unauthenticated() -> CurrentUser:
        raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED"})

    app.dependency_overrides[get_current_user] = unauthenticated
    response = client.get("/requests/recommendations")
    assert response.status_code == 401


def test_recommendations_handle_zero_maximum_distance() -> None:
    configure_recommender()
    crud_module.users_store["usr_209"]["maxDistanceKm"] = 0
    add_recommendation_request("req_same_place", distanceKm=0)

    response = client.get("/requests/recommendations")

    assert response.status_code == 200
    same_place = next(
        item for item in response.json()["items"] if item["id"] == "req_same_place"
    )
    assert "活動範囲内（約0km）" in same_place["recommendationReasons"]


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
    async def helper_user() -> CurrentUser:
        return HELPER

    app.dependency_overrides[get_current_user] = helper_user
    response = client.post(
        "/requests/req_1024/applications",
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
