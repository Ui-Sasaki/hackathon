"""依頼の公開（作成時の自動公開、draft からの公開API）と、公開後の取消のテスト。"""

import asyncio
import os

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["REQUEST_REPOSITORY"] = "memory"

import httpx

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.repositories.requests import get_request_repository


class ASGITestClient:
    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as async_client:
                return await async_client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)


client = ASGITestClient()

REQUESTER = CurrentUser(
    user_id="usr_101", role="member", status="active",
    email_verified=True, verification_status="approved",
)
HELPER = CurrentUser(
    user_id="usr_207", role="member", status="active",
    email_verified=True, verification_status="approved",
)

REQUEST_BODY = {
    "title": "庭の片付け",
    "description": "庭の落ち葉を一緒に片付けてください",
    "category": "cleaning",
    "scheduledAt": "2026-09-10T10:00:00+09:00",
    "estimatedMinutes": 30,
    "requiredHelpers": 1,
    "areaCode": "AREA-001",
    "riskLevel": "low",
    "confirmed": True,
}


def act_as(user: CurrentUser) -> None:
    async def current() -> CurrentUser:
        return user

    app.dependency_overrides[get_current_user] = current


def setup_function() -> None:
    act_as(REQUESTER)
    client.post("/_mock/reset")


def create_request(key: str = "publish-test-1") -> dict:
    response = client.post(
        "/requests", json=REQUEST_BODY, headers={"Idempotency-Key": key}
    )
    assert response.status_code == 201, response.text
    return response.json()


def force_status(request_id: str, status: str) -> None:
    moved = asyncio.run(
        get_request_repository().set_status(
            REQUESTER, request_id, status, bump_version=False,
        )
    )
    assert moved


def listed_ids_for_helper() -> set[str]:
    act_as(HELPER)
    # 一覧は地域の指定（または位置情報）が必須なので、種データと同じ地域で見る。
    response = client.get("/requests", params={"areaCode": "AREA-001"})
    assert response.status_code == 200, response.text
    act_as(REQUESTER)
    return {item["id"] for item in response.json()["items"]}


def test_a_confirmed_request_is_published_on_creation() -> None:
    created = create_request()

    assert created["status"] == "published"
    assert created["requesterId"] == REQUESTER.user_id
    assert created["id"] in listed_ids_for_helper()


def test_creation_is_idempotent_and_stays_published() -> None:
    first = create_request("same-key")
    second = create_request("same-key")

    assert second["id"] == first["id"]
    assert second["status"] == "published"


def test_a_draft_can_be_published_by_its_requester() -> None:
    created = create_request()
    force_status(created["id"], "draft")
    assert created["id"] not in listed_ids_for_helper()

    response = client.post(f"/requests/{created['id']}/publish")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "published"
    assert body["version"] == created["version"] + 1
    assert created["id"] in listed_ids_for_helper()


def test_only_the_requester_can_publish() -> None:
    created = create_request()
    force_status(created["id"], "draft")

    act_as(HELPER)
    response = client.post(f"/requests/{created['id']}/publish")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_FORBIDDEN"
    assert created["id"] not in listed_ids_for_helper()


def test_publishing_an_already_published_request_is_rejected() -> None:
    created = create_request()

    response = client.post(f"/requests/{created['id']}/publish")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_REQUEST_TRANSITION"


def test_requests_under_review_cannot_be_published_by_the_requester() -> None:
    created = create_request()
    force_status(created["id"], "pending_review")

    response = client.post(f"/requests/{created['id']}/publish")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUEST_UNDER_REVIEW"
    assert created["id"] not in listed_ids_for_helper()


def test_unknown_request_returns_404() -> None:
    response = client.post("/requests/does-not-exist/publish")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REQUEST_NOT_FOUND"


def test_cancelling_a_published_request_removes_it_from_the_list() -> None:
    created = create_request()
    assert created["id"] in listed_ids_for_helper()

    response = client.delete(f"/requests/{created['id']}")

    assert response.status_code == 204
    assert created["id"] not in listed_ids_for_helper()
    detail = client.get(f"/requests/{created['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "cancelled"

    # 取消済みは公開へ戻せない。
    republish = client.post(f"/requests/{created['id']}/publish")
    assert republish.status_code == 409
    assert republish.json()["error"]["code"] == "INVALID_REQUEST_TRANSITION"


def test_cancelling_twice_is_rejected() -> None:
    created = create_request()
    assert client.delete(f"/requests/{created['id']}").status_code == 204

    response = client.delete(f"/requests/{created['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_REQUEST_TRANSITION"
