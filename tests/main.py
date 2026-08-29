import logging
import os
import asyncio
from copy import deepcopy

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["REQUEST_REPOSITORY"] = "memory"

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.auth as auth_module
import app.cruds.main as crud_module
from app.auth import CurrentUser, get_current_user
from app.cruds.main import SEED_REQUEST_1024
from app.main import app
from app.repositories.requests import (
    MemoryRequestRepository, PostgresRequestRepository, encode_cursor, get_request_repository,
)
from app.repositories.applications import (
    MemoryApplicationRepository, PostgresApplicationRepository,
    get_application_repository,
)
from app.settings import load_settings


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

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)


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
    crud_module.configure_structure_llm_client(crud_module.default_structure_llm_client)
    for metric in crud_module.masking_metrics:
        crud_module.masking_metrics[metric] = 0


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_requests() -> None:
    response = client.get("/requests", params={"areaCode": "AREA-001"})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def add_search_request(request_id: str, **changes) -> None:
    repository = get_request_repository()
    assert isinstance(repository, MemoryRequestRepository)
    item = deepcopy(repository._items[SEED_REQUEST_1024])
    item.update(
        {
            "id": request_id,
            "createdAt": f"2026-08-21T00:00:{int(request_id.split('_')[-1]):02d}+00:00",
            **changes,
        }
    )
    item["_requesterVerificationStatus"] = crud_module.users_store.get(
        item["requesterId"], {}
    ).get("verificationStatus", item.get("_requesterVerificationStatus", "unverified"))
    repository._items[request_id] = item


def test_location_is_resolved_only_after_explicit_consent() -> None:
    response = client.post(
        "/locations/resolve",
        json={"consentGranted": True, "latitude": 43.082, "longitude": 141.350},
    )
    assert response.status_code == 200
    assert response.json()["areaCode"] == "AREA-002"
    assert response.json()["source"] == "current_location"
    assert "latitude" not in response.text
    assert "longitude" not in response.text


@pytest.mark.parametrize("reason", ["denied", "timeout", "unsupported", "unavailable"])
def test_location_failure_falls_back_to_registered_region(reason: str) -> None:
    response = client.post("/locations/resolve", json={"failureReason": reason})
    assert response.status_code == 200
    assert response.json()["areaCode"] == "AREA-001"
    assert response.json()["fallbackUsed"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {"consentGranted": False, "latitude": 43.0, "longitude": 141.0},
        {"consentGranted": True, "latitude": 91, "longitude": 141.0},
        {"consentGranted": True, "latitude": 43.0},
    ],
)
def test_location_rejects_invalid_coordinates(payload: dict) -> None:
    response = client.post("/locations/resolve", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "43.0" not in response.text


def test_location_requires_region_selection_without_fallback() -> None:
    crud_module.users_store["usr_101"].pop("areaCode")
    response = client.post("/locations/resolve", json={"failureReason": "denied"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REGION_SELECTION_REQUIRED"


def test_request_list_reports_current_location_origin() -> None:
    response = client.get(
        "/requests",
        params={
            "consentGranted": "true",
            "latitude": 43.082,
            "longitude": 141.350,
        },
    )
    assert response.status_code == 200
    assert response.json()["origin"] == {
        "areaCode": "AREA-002",
        "source": "current_location",
    }


def test_request_search_filters_requests() -> None:
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

    detail = client.get(f"/requests/{SEED_REQUEST_1024}").json()
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


def test_request_search_applies_distance_filter_before_cursor_paging() -> None:
    for index in range(1, 22):
        add_search_request(f"far_{index:02d}", distanceKm=99)

    response = client.get("/requests", params={"maxDistanceKm": 2})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        crud_module.SEED_REQUEST_1025, crud_module.SEED_REQUEST_1024,
    ]
    assert response.json()["nextCursor"] is None


def test_request_search_cursor_pages_filtered_result_set_without_skips() -> None:
    for index in range(1, 22):
        add_search_request(f"far_{index:02d}", distanceKm=99)
    for index in range(1, 6):
        add_search_request(
            f"near_{index:02d}",
            createdAt=f"2026-08-19T00:00:{index:02d}+00:00",
            distanceKm=1,
        )

    expected_ids = [
        *(f"near_{index:02d}" for index in range(5, 0, -1)),
        crud_module.SEED_REQUEST_1025, crud_module.SEED_REQUEST_1024,
    ]
    collected_ids = []
    cursor = None
    while True:
        params = {"maxDistanceKm": 2, "limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get("/requests", params=params)
        assert response.status_code == 200
        body = response.json()
        collected_ids.extend(item["id"] for item in body["items"])
        cursor = body["nextCursor"]
        if cursor is None:
            break

    assert collected_ids == expected_ids
    assert len(collected_ids) == len(set(collected_ids))


def test_request_search_validates_limit_cursor_and_location_pair() -> None:
    assert client.get("/requests", params={"limit": 101}).status_code == 422
    invalid = client.get("/requests", params={"cursor": "not-a-cursor"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_CURSOR"
    assert client.get("/requests", params={"latitude": 35.0}).status_code == 422


def test_request_search_rejects_cursor_for_missing_request() -> None:
    cursor = encode_cursor(
        {"id": "missing", "createdAt": "2026-08-21T00:00:00Z"}
    )

    response = client.get("/requests", params={"cursor": cursor})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_structure_request() -> None:
    response = client.post(
        "/requests/structure",
        json={"text": "病気なので犬の散歩をお願いしたい", "areaCode": "AREA-001"},
    )
    assert response.status_code == 200
    assert response.json()["request"]["task"] == "病気なので犬の散歩をお願いしたい"


def test_masking_preview_detects_japanese_and_full_width_pii_formats() -> None:
    original_values = [
        "hanako@example.jp",
        "０９０－１２３４－５６７８",
        "〒１６０－００２３",
        "東京都新宿区西新宿２丁目８－１",
        "学生証番号：ＡＢＣ１２３４５",
        "氏名は山田 花子",
    ]
    response = client.post(
        "/requests/masking-preview",
        json={
            "text": "、".join(original_values) + "。荷物の整理をお願いします",
            "areaCode": "AREA-001",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["hasDetections"] is True
    assert {item["type"] for item in body["detections"]} == {
        "email",
        "phone",
        "postal_code",
        "address",
        "certificate_number",
        "name",
    }
    assert "[メールアドレス]" in body["maskedText"]
    assert "[電話番号]" in body["maskedText"]
    assert "[郵便番号]" in body["maskedText"]
    assert "[詳細住所]" in body["maskedText"]
    assert "[証明書番号]" in body["maskedText"]
    assert "[氏名]" in body["maskedText"]
    for value in original_values:
        assert value not in response.text


def test_structure_requires_confirmation_and_only_sends_masked_text_to_llm() -> None:
    calls = []

    async def capture(masked_text: str, area_code: str) -> dict:
        calls.append((masked_text, area_code))
        return await crud_module.default_structure_llm_client(masked_text, area_code)

    crud_module.configure_structure_llm_client(capture)
    payload = {
        "text": "連絡先090-1234-5678へ電話して、犬の散歩をお願いします",
        "areaCode": "AREA-001",
    }
    preview = client.post("/requests/structure", json=payload)
    confirmed = client.post(
        "/requests/structure", json={**payload, "maskingConfirmed": True}
    )

    assert preview.status_code == 200
    assert preview.json()["status"] == "masking_confirmation_required"
    assert calls == [("連絡先[電話番号]へ電話して、犬の散歩をお願いします", "AREA-001")]
    assert confirmed.status_code == 200
    assert "090-1234-5678" not in confirmed.text
    assert confirmed.json()["request"]["task"] == "連絡先[電話番号]へ電話して、犬の散歩をお願いします"
    assert confirmed.json()["masking"]["confirmed"] is True


def test_user_can_correct_false_detection_before_structure_submission() -> None:
    detected = client.post(
        "/requests/structure",
        json={"text": "整理番号は090-1234-5678です", "areaCode": "AREA-001"},
    )
    corrected = client.post(
        "/requests/structure",
        json={"text": "整理番号を確認して片付けます", "areaCode": "AREA-001"},
    )

    assert detected.json()["requiresMaskingConfirmation"] is True
    assert corrected.status_code == 200
    assert corrected.json()["requiresConfirmation"] is True
    assert corrected.json()["masking"]["detections"] == []


def test_masking_service_failure_does_not_log_or_return_unmasked_input(caplog) -> None:
    private_values = "secret@example.jp 090-9876-5432"

    async def unavailable(_masked_text: str, _area_code: str) -> dict:
        raise RuntimeError("provider-key-secret")

    crud_module.configure_structure_llm_client(unavailable)
    with caplog.at_level(logging.WARNING, logger="app.cruds.main"):
        response = client.post(
            "/requests/structure",
            json={
                "text": f"連絡先は{private_values}、荷物を整理してください",
                "areaCode": "AREA-001",
                "maskingConfirmed": True,
            },
        )

    assert response.status_code == 503
    assert private_values not in response.text
    assert private_values not in caplog.text
    assert "provider-key-secret" not in response.text
    assert "provider-key-secret" not in caplog.text


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


def test_request_owner_can_update_with_expected_version() -> None:
    response = client.patch(
        f"/requests/{SEED_REQUEST_1024}",
        json={"title": "更新した依頼", "expectedVersion": 3},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "更新した依頼"
    assert response.json()["version"] == 4


def test_non_owner_cannot_update_or_cancel_request() -> None:
    async def helper_user() -> CurrentUser:
        return HELPER

    app.dependency_overrides[get_current_user] = helper_user
    update = client.patch(
        f"/requests/{SEED_REQUEST_1024}",
        json={"title": "乗っ取り", "expectedVersion": 3},
    )
    cancel = client.delete(f"/requests/{SEED_REQUEST_1024}")
    assert update.status_code == 403
    assert cancel.status_code == 403
    assert update.json()["error"]["code"] == "ROLE_FORBIDDEN"
    assert cancel.json()["error"]["code"] == "ROLE_FORBIDDEN"


def test_completed_request_cannot_be_cancelled() -> None:
    repository = get_request_repository()
    asyncio.run(
        repository.set_status(REQUESTER, SEED_REQUEST_1024, "completed", bump_version=False)
    )
    response = client.delete(f"/requests/{SEED_REQUEST_1024}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_REQUEST_TRANSITION"


def test_repository_implementations_share_request_contract() -> None:
    operations = {"list", "get", "create", "update", "cancel", "set_status", "reset"}
    for implementation in (MemoryRequestRepository, PostgresRequestRepository):
        assert operations <= set(dir(implementation))


def test_repository_implementations_share_application_contract() -> None:
    operations = {"list_for_request", "get", "create", "withdraw", "reset"}
    for implementation in (MemoryApplicationRepository, PostgresApplicationRepository):
        assert operations <= set(dir(implementation))


def test_production_settings_never_fall_back_to_memory(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REQUEST_REPOSITORY", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        load_settings()


def test_production_rejects_explicit_memory_repository(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REQUEST_REPOSITORY", "memory")
    monkeypatch.setenv("DATABASE_URL", "postgresql://configured")

    with pytest.raises(RuntimeError, match="postgres"):
        load_settings()


def test_test_settings_explicitly_select_memory(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("REQUEST_REPOSITORY", raising=False)

    assert load_settings().request_repository == "memory"


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


def create_open_request_for_application() -> str:
    response = client.post(
        "/requests",
        headers={"Idempotency-Key": f"application-{os.urandom(4).hex()}"},
        json={
            "title": "応募テスト依頼",
            "description": "応募永続化を確認する依頼です",
            "category": "other",
            "scheduledAt": "2099-08-22T10:00:00+09:00",
            "estimatedMinutes": 30,
            "requiredHelpers": 1,
            "areaCode": "AREA-001",
            "riskLevel": "low",
            "confirmed": True,
        },
    )
    assert response.status_code == 201
    request_id = response.json()["id"]
    asyncio.run(get_request_repository().set_status(REQUESTER, request_id, "published"))
    return request_id


def test_application_is_created_from_authenticated_helper_and_can_be_withdrawn() -> None:
    request_id = create_open_request_for_application()

    async def helper_user() -> CurrentUser:
        return HELPER

    app.dependency_overrides[get_current_user] = helper_user
    created = client.post(
        f"/requests/{request_id}/applications",
        json={"message": "対応できます", "availableAt": "2099-08-22T09:00:00+09:00"},
    )
    assert created.status_code == 201
    assert created.json()["helperId"] == HELPER.user_id
    application_id = created.json()["id"]

    withdrawn = client.post(f"/applications/{application_id}/withdraw")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    repeated = client.post(f"/applications/{application_id}/withdraw")
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "APPLICATION_NOT_WITHDRAWABLE"


def test_self_application_is_forbidden() -> None:
    response = client.post(
        f"/requests/{SEED_REQUEST_1024}/applications",
        json={"message": "自分で対応", "availableAt": "2099-08-22T09:00:00+09:00"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SELF_APPLICATION_NOT_ALLOWED"


def test_application_to_closed_or_expired_request_is_rejected() -> None:
    request_id = create_open_request_for_application()
    request_repository = get_request_repository()
    assert isinstance(request_repository, MemoryRequestRepository)

    async def helper_user() -> CurrentUser:
        return HELPER

    app.dependency_overrides[get_current_user] = helper_user
    asyncio.run(request_repository.set_status(REQUESTER, request_id, "cancelled"))
    closed = client.post(
        f"/requests/{request_id}/applications",
        json={"message": "対応できます", "availableAt": "2099-08-22T09:00:00+09:00"},
    )
    assert closed.status_code == 409
    assert closed.json()["error"]["code"] == "REQUEST_NOT_OPEN"

    asyncio.run(request_repository.set_status(REQUESTER, request_id, "published"))
    request_repository._items[request_id]["expiresAt"] = "2000-01-01T00:00:00Z"
    expired = client.post(
        f"/requests/{request_id}/applications",
        json={"message": "対応できます", "availableAt": "2099-08-22T09:00:00+09:00"},
    )
    assert expired.status_code == 409
    assert expired.json()["error"]["code"] == "REQUEST_EXPIRED"


def test_verification_required_request_rejects_unverified_helper() -> None:
    request_id = create_open_request_for_application()
    request_repository = get_request_repository()
    assert isinstance(request_repository, MemoryRequestRepository)
    request_repository._items[request_id]["verificationRequired"] = True

    async def unverified_user() -> CurrentUser:
        return CurrentUser(
            user_id="usr_208", role="member", status="active",
            email_verified=True, verification_status="unverified",
        )

    app.dependency_overrides[get_current_user] = unverified_user
    response = client.post(
        f"/requests/{request_id}/applications",
        json={"message": "対応できます", "availableAt": "2099-08-22T09:00:00+09:00"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "VERIFICATION_REQUIRED"


def test_application_validation_and_missing_application_errors() -> None:
    invalid = client.post(
        f"/requests/{SEED_REQUEST_1024}/applications",
        json={"message": "", "availableAt": "not-a-date"},
    )
    assert invalid.status_code == 422
    missing = client.post("/applications/missing/withdraw")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "APPLICATION_NOT_FOUND"


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
    assert user.role == "member"
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
    assert user.role == "member"


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
        "role": "member",
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
    assert SEED_REQUEST_1024 not in {
        item["id"] for item in list_response.json()["items"]
    }
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
    private_value = "秘密"
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


def test_newly_created_profile_matches_public_profile_contract() -> None:
    user_id = "new-supertokens-user"
    crud_module.create_user_profile(user_id)

    async def new_user() -> CurrentUser:
        return CurrentUser(
            user_id=user_id,
            role="member",
            status="active",
            email_verified=False,
            verification_status="unverified",
        )

    app.dependency_overrides[get_current_user] = new_user
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
