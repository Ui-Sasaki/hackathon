"""依頼の公開（draft -> published）と、公開後の取消のテスト。"""

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


def create_draft(key: str = "publish-test-1") -> dict:
    response = client.post(
        "/requests", json=REQUEST_BODY, headers={"Idempotency-Key": key}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "draft"
    return body


def listed_ids_for_helper() -> set[str]:
    act_as(HELPER)
    # 一覧は地域の指定（または位置情報）が必須なので、種データと同じ地域で見る。
    response = client.get("/requests", params={"areaCode": "AREA-001"})
    assert response.status_code == 200, response.text
    act_as(REQUESTER)
    return {item["id"] for item in response.json()["items"]}


def test_publishing_a_draft_makes_it_visible_to_helpers() -> None:
    draft = create_draft()
    assert draft["id"] not in listed_ids_for_helper()

    response = client.post(f"/requests/{draft['id']}/publish")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == draft["id"]
    assert body["status"] == "published"
    assert body["version"] == draft["version"] + 1
    assert body["requesterId"] == REQUESTER.user_id
    assert draft["id"] in listed_ids_for_helper()


def test_only_the_requester_can_publish() -> None:
    draft = create_draft()

    act_as(HELPER)
    response = client.post(f"/requests/{draft['id']}/publish")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ROLE_FORBIDDEN"
    assert draft["id"] not in listed_ids_for_helper()


def test_publishing_twice_is_rejected() -> None:
    draft = create_draft()
    assert client.post(f"/requests/{draft['id']}/publish").status_code == 200

    response = client.post(f"/requests/{draft['id']}/publish")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_REQUEST_TRANSITION"


def test_requests_under_review_cannot_be_published_by_the_requester() -> None:
    draft = create_draft()
    moved = asyncio.run(
        get_request_repository().set_status(
            REQUESTER, draft["id"], "pending_review", bump_version=False,
        )
    )
    assert moved

    response = client.post(f"/requests/{draft['id']}/publish")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REQUEST_UNDER_REVIEW"
    assert draft["id"] not in listed_ids_for_helper()


def test_unknown_request_returns_404() -> None:
    response = client.post("/requests/does-not-exist/publish")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REQUEST_NOT_FOUND"


def test_cancelling_a_published_request_removes_it_from_the_list() -> None:
    draft = create_draft()
    assert client.post(f"/requests/{draft['id']}/publish").status_code == 200
    assert draft["id"] in listed_ids_for_helper()

    response = client.delete(f"/requests/{draft['id']}")

    assert response.status_code == 204
    assert draft["id"] not in listed_ids_for_helper()
    detail = client.get(f"/requests/{draft['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "cancelled"

    # 取消済みは公開へ戻せない。
    republish = client.post(f"/requests/{draft['id']}/publish")
    assert republish.status_code == 409
    assert republish.json()["error"]["code"] == "INVALID_REQUEST_TRANSITION"


def test_cancelling_twice_is_rejected() -> None:
    draft = create_draft()
    assert client.delete(f"/requests/{draft['id']}").status_code == 204

    response = client.delete(f"/requests/{draft['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_REQUEST_TRANSITION"
