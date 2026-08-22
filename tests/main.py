import logging
import os
import asyncio
from copy import deepcopy

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
# Local schema-identical Postgres (see supabase/tests/run.sh). trust auth, no
# secret involved. sslmode=disable avoids a crash in asyncpg's SSL-negotiation
# fallback path on native Windows Python when the server doesn't offer TLS.
os.environ.setdefault(
    "DATABASE_URL", "postgresql://tetote_app@127.0.0.1:55432/tetote?sslmode=disable"
)

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.auth as auth_module
import app.cruds.main as crud_module
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
    crud_module.configure_risk_generator(crud_module.default_risk_generator)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_requests() -> None:
    response = client.get("/requests", params={"areaCode": "AREA-001"})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def add_search_request(request_id: str, **changes) -> None:
    item = deepcopy(crud_module.INITIAL_REQUESTS[0])
    item.update(
        {
            "id": request_id,
            "createdAt": f"2026-08-21T00:00:{int(request_id.split('_')[-1]):02d}+00:00",
            **changes,
        }
    )
    crud_module.requests_store[request_id] = item


def test_request_search_filters_and_excludes_closed_or_expired_requests() -> None:
    add_search_request(
        "req_01", category="cleaning", requiredHelpers=2,
        scheduledAt="2026-09-01T10:00:00+09:00", requesterId="usr_101",
    )
    add_search_request("req_02", status="cancelled")
    add_search_request("req_03", scheduledAt="2020-01-01T00:00:00+00:00")

    response = client.get(
        "/requests",
        params={
            "category": "cleaning", "requiredHelpers": 2,
            "verificationStatus": "approved",
            "scheduledFrom": "2026-09-01T00:00:00+09:00",
            "scheduledTo": "2026-09-02T00:00:00+09:00",
        },
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["req_01"]


def test_request_search_uses_profile_area_and_never_returns_precise_location() -> None:
    response = client.get("/requests", params={"maxDistanceKm": 2})

    assert response.status_code == 200
    assert response.json()["items"]
    for item in response.json()["items"]:
        assert "latitude" not in item
        assert "longitude" not in item
        assert "streetAddress" not in item
        assert item["distanceKm"] <= 2

    detail = client.get("/requests/req_1024").json()
    assert "latitude" not in detail
    assert "longitude" not in detail
    assert "streetAddress" not in detail


def test_request_search_cursor_paging_has_default_page_size_20() -> None:
    for index in range(1, 22):
        add_search_request(f"req_{index:02d}")

    first = client.get("/requests")
    assert first.status_code == 200
    assert len(first.json()["items"]) == 20
    assert first.json()["nextCursor"] is not None

    second = client.get("/requests", params={"cursor": first.json()["nextCursor"]})
    first_ids = {item["id"] for item in first.json()["items"]}
    second_ids = {item["id"] for item in second.json()["items"]}
    assert len(second_ids) == 3
    assert first_ids.isdisjoint(second_ids)


def test_request_search_validates_limit_cursor_and_location_pair() -> None:
    assert client.get("/requests", params={"limit": 101}).status_code == 422
    assert client.get("/requests", params={"cursor": "not-a-cursor"}).status_code == 422
    assert client.get("/requests", params={"latitude": 35.0}).status_code == 422


def test_structure_request() -> None:
    response = client.post(
        "/requests/structure",
        json={"text": "病気なので犬の散歩をお願いしたい", "areaCode": "AREA-001"},
    )
    assert response.status_code == 200
    assert response.json()["category"] == "pet_support"


@pytest.mark.parametrize(
    ("text", "reason_code"),
    [
        ("利用者への医療行為を手伝ってください", "MEDICAL_WORK"),
        ("高齢者の介護を手伝ってください", "CARE_WORK"),
        ("自宅の電気工事をお願いします", "ELECTRICAL_WORK"),
        ("屋根の雪下ろしをお願いします", "HIGH_PLACE_WORK"),
        ("チェーンソーで木を切ってください", "DANGEROUS_TOOL"),
        ("通帳を預けるので金銭管理をお願いします", "MONEY_MANAGEMENT"),
        ("病院まで車で送迎してください", "TRANSPORT"),
        ("日用品の買い物代行をお願いします", "SHOPPING_PROXY"),
    ],
)
def test_fixed_rules_classify_out_of_scope_work_as_high(
    text: str, reason_code: str
) -> None:
    async def incorrectly_low(_text: str) -> dict:
        return {"level": "low", "reasonCodes": ["LLM_LOW"]}

    crud_module.configure_risk_generator(incorrectly_low)
    response = client.post("/requests/risk-assessment", json={"text": text})

    assert response.status_code == 200
    assessment = response.json()
    assert assessment["level"] == "high"
    assert assessment["publicationAllowed"] is False
    assert assessment["nextStatus"] == "rejected"
    assert reason_code in assessment["reasonCodes"]
    assert assessment["fixedRuleLevel"] == "high"
    assert assessment["llmLevel"] == "low"


@pytest.mark.parametrize(
    ("weight", "expected_level"),
    [(19, "low"), (20, "review_required"), (29, "review_required"), (30, "high")],
)
def test_weight_boundaries_are_deterministic(weight: int, expected_level: str) -> None:
    response = client.post(
        "/requests/risk-assessment",
        json={"text": f"重さ{weight}kgの荷物を移動してください"},
    )
    assert response.status_code == 200
    assert response.json()["level"] == expected_level


def test_review_required_and_llm_high_control_publication_state() -> None:
    review = client.post(
        "/requests/risk-assessment",
        json={
            "text": "脚立を使うかもしれない清掃です",
            "scheduledAt": "2026-08-25T23:00:00+09:00",
        },
    )

    async def high_risk(_text: str) -> dict:
        return {"level": "high", "reasonCodes": ["CONTEXTUAL_DANGER"]}

    crud_module.configure_risk_generator(high_risk)
    high = client.post(
        "/requests/risk-assessment", json={"text": "特殊な作業を手伝ってください"}
    )

    assert review.json()["level"] == "review_required"
    assert review.json()["nextStatus"] == "pending_review"
    assert {"HEIGHT_UNCLEAR", "LATE_NIGHT_WORK"}.issubset(review.json()["reasonCodes"])
    assert high.json()["level"] == "high"
    assert high.json()["reasonCodes"] == ["CONTEXTUAL_DANGER"]


def test_risk_llm_receives_masked_input_and_audit_omits_original_text() -> None:
    captured = []

    async def capture(masked_text: str) -> dict:
        captured.append(masked_text)
        return {"level": "low", "reasonCodes": []}

    crud_module.configure_risk_generator(capture)
    original = "東京都新宿区1-2-3です。電話090-1234-5678へ連絡してください"
    response = client.post("/requests/risk-assessment", json={"text": original})

    assert response.status_code == 200
    assert "東京都新宿区" not in captured[0]
    assert "090-1234-5678" not in captured[0]
    audit = crud_module.risk_assessments[response.json()["id"]]
    assert "text" not in audit
    assert "ruleVersion" in audit
    assert "modelName" in audit
    assert "promptVersion" in audit
    assert "assessedAt" in audit


def test_unclear_or_failed_llm_assessment_routes_to_review() -> None:
    async def unclear(_text: str) -> dict:
        return {"level": "unknown", "reasonCodes": []}

    crud_module.configure_risk_generator(unclear)
    unclear_response = client.post(
        "/requests/risk-assessment", json={"text": "内容を相談したい作業です"}
    )

    async def unavailable(_text: str) -> dict:
        raise TimeoutError("private provider error")

    crud_module.configure_risk_generator(unavailable)
    failed_response = client.post(
        "/requests/risk-assessment", json={"text": "内容を相談したい作業です"}
    )

    assert unclear_response.json()["level"] == "review_required"
    assert "LLM_ASSESSMENT_UNCLEAR" in unclear_response.json()["reasonCodes"]
    assert failed_response.json()["level"] == "review_required"
    assert "LLM_ASSESSMENT_UNAVAILABLE" in failed_response.json()["reasonCodes"]


def request_payload(title: str, description: str, scheduled_at: str) -> dict:
    return {
        "title": title,
        "description": description,
        "category": "other",
        "scheduledAt": scheduled_at,
        "estimatedMinutes": 30,
        "requiredHelpers": 1,
        "areaCode": "AREA-001",
        "riskLevel": "low",
        "confirmed": True,
    }


def test_create_request_rejects_high_risk_and_routes_review_required() -> None:
    rejected = client.post(
        "/requests",
        headers={"Idempotency-Key": "high-risk"},
        json=request_payload(
            "電気工事", "コンセント交換をお願いします", "2026-08-25T10:00:00+09:00"
        ),
    )
    pending = client.post(
        "/requests",
        headers={"Idempotency-Key": "review-risk"},
        json=request_payload(
            "夜間の片付け", "部屋を片付けてください", "2026-08-25T23:00:00+09:00"
        ),
    )

    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "HIGH_RISK_REQUEST"
    assert pending.status_code == 201
    assert pending.json()["status"] == "pending_review"
    assert pending.json()["riskLevel"] == "review_required"


def test_update_request_cannot_bypass_high_risk_assessment() -> None:
    response = client.patch(
        "/requests/req_1024",
        json={"description": "電気工事をしてください", "expectedVersion": 3},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "HIGH_RISK_REQUEST"
    assert crud_module.requests_store["req_1024"]["description"] == (
        "体調不良のため、小型犬の散歩を30分お願いしたいです。"
    )
    assert crud_module.requests_store["req_1024"]["status"] == "published"


def test_invalid_llm_reason_codes_are_not_exposed() -> None:
    async def unsafe_reason(_text: str) -> dict:
        return {"level": "high", "reasonCodes": ["090-1234-5678"]}

    crud_module.configure_risk_generator(unsafe_reason)
    response = client.post(
        "/requests/risk-assessment", json={"text": "内容を相談したい作業です"}
    )

    assert response.status_code == 200
    assert response.json()["level"] == "high"
    assert response.json()["reasonCodes"] == ["LLM_REASON_CODES_INVALID"]
    assert "090-1234-5678" not in response.text


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
            "targetId": SEED_REQUEST_1024,
            "reason": "dangerous_work",
            "description": "高所で危険な作業を要求されています",
        },
    )
    assert response.status_code == 201
    report = response.json()
    assert report["reporterId"] == REQUESTER.user_id
    assert report["targetId"] == SEED_REQUEST_1024
    assert report["reason"] == "dangerous_work"
    assert report["description"] == "高所で危険な作業を要求されています"
    assert report["severity"] == "high"
    assert report["createdAt"].endswith("Z")
    assert client.get(f"/requests/{SEED_REQUEST_1024}").json()["status"] == "suspended"
    assert [event["eventType"] for event in crud_module.audit_logs] == [
        "report_created",
        "request_auto_suspended",
    ]


def test_reporter_id_cannot_be_supplied_by_client() -> None:
    response = client.post(
        "/reports",
        json={
            "reporterId": "attacker-controlled",
            "targetType": "user",
            "targetId": HELPER.user_id,
            "reason": "harassment",
            "description": "不適切なメッセージが繰り返し送られました",
        },
    )

    assert response.status_code == 201
    assert response.json()["reporterId"] == REQUESTER.user_id


def test_block_and_unblock_are_scoped_to_authenticated_user_and_audited() -> None:
    blocked = client.post(f"/users/{HELPER.user_id}/block", json={"blocked": True})
    assert blocked.status_code == 201
    assert blocked.json()["blocked"] is True
    assert (REQUESTER.user_id, HELPER.user_id) in crud_module.blocks

    unblocked = client.post(f"/users/{HELPER.user_id}/block", json={"blocked": False})
    assert unblocked.status_code == 201
    assert unblocked.json()["blocked"] is False
    assert (REQUESTER.user_id, HELPER.user_id) not in crud_module.blocks
    assert [event["eventType"] for event in crud_module.audit_logs] == [
        "user_blocked",
        "user_unblocked",
    ]


def test_self_block_is_rejected_without_audit_event() -> None:
    response = client.post(f"/users/{REQUESTER.user_id}/block", json={"blocked": True})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SELF_BLOCK_NOT_ALLOWED"
    assert crud_module.audit_logs == []


def test_blocked_users_requests_applications_and_messages_are_hidden() -> None:
    # The requester no longer sees applications from a helper they blocked.
    assert client.post(f"/users/{HELPER.user_id}/block", json={"blocked": True}).status_code == 201
    applications_response = client.get(f"/requests/{SEED_REQUEST_1024}/applications")
    assert applications_response.status_code == 200
    assert "usr_207" not in {
        item["helperId"] for item in applications_response.json()["items"]
    }

    # The blocked helper can no longer discover the requester's requests.
    async def helper_user() -> CurrentUser:
        return HELPER

    app.dependency_overrides[get_current_user] = helper_user
    list_response = client.get("/requests", params={"areaCode": "AREA-001"})
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []
    detail_response = client.get(f"/requests/{SEED_REQUEST_1024}")
    assert detail_response.status_code == 404


def test_messages_from_blocked_user_are_hidden() -> None:
    match_id = create_match()

    async def helper_user() -> CurrentUser:
        return HELPER

    app.dependency_overrides[get_current_user] = helper_user
    sent = client.post(f"/matches/{match_id}/messages", json={"body": "対応できます"})
    assert sent.status_code == 201

    app.dependency_overrides[get_current_user] = requester_user
    assert client.post(f"/users/{HELPER.user_id}/block", json={"blocked": True}).status_code == 201
    response = client.get(f"/matches/{match_id}/messages")
    assert response.status_code == 200
    assert response.json()["items"] == []


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
