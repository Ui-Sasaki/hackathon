"""応募者一覧の支援者情報（HelperSummary）が、種データ以外の利用者でも組み立てられることのテスト。

本番では応募者は実在の利用者（SuperTokens の ID）で、開発用の種データ `HELPERS` には
存在しない。その場合に KeyError で 500 を返していたのが「応募者一覧を取得できませんでした」の原因。
"""

import asyncio
import os

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["REQUEST_REPOSITORY"] = "memory"

import httpx

from app.auth import CurrentUser, get_current_user
from app.main import app
from app.repositories.applications import _row_to_record
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


client = ASGITestClient()

REQUESTER = CurrentUser(
    user_id="usr_101", role="member", status="active",
    email_verified=True, verification_status="approved",
)
# 種データ users_store にはいるが、開発用の HELPERS 辞書には無い利用者
KNOWN_USER_NOT_IN_HELPERS = CurrentUser(
    user_id="usr_301", role="member", status="active",
    email_verified=True, verification_status="unverified",
)
# どの種データにも無い、本番相当の利用者（SuperTokens の ID）
UNKNOWN_USER = CurrentUser(
    user_id="2b283074-f684-40c5-8d4f-1ef3b4f0e961", role="member", status="active",
    email_verified=True, verification_status="approved",
)


def act_as(user: CurrentUser) -> None:
    async def current() -> CurrentUser:
        return user

    app.dependency_overrides[get_current_user] = current


def setup_function() -> None:
    act_as(REQUESTER)
    client.post("/_mock/reset")


def create_published_request() -> str:
    response = client.post(
        "/requests",
        headers={"Idempotency-Key": "helper-summary-1"},
        json={
            "title": "一緒にラジオ体操してほしい",
            "description": "朝の公園で一緒にラジオ体操をしてほしいです",
            "category": "exercise",
            "scheduledAt": "2099-09-10T07:00:00+09:00",
            "estimatedMinutes": 30,
            "requiredHelpers": 1,
            "areaCode": "AREA-001",
            "riskLevel": "low",
            "confirmed": True,
        },
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]
    if response.json()["status"] != "published":
        asyncio.run(get_request_repository().set_status(REQUESTER, request_id, "published"))
    return request_id


def apply_as(user: CurrentUser, request_id: str) -> dict:
    act_as(user)
    response = client.post(
        f"/requests/{request_id}/applications",
        json={"message": "対応できます", "availableAt": "2099-09-10T07:00:00+09:00"},
    )
    assert response.status_code == 201, response.text
    act_as(REQUESTER)
    return response.json()


def test_requester_sees_applicants_who_are_not_in_the_seed_helpers() -> None:
    request_id = create_published_request()
    apply_as(KNOWN_USER_NOT_IN_HELPERS, request_id)

    response = client.get(f"/requests/{request_id}/applications")

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["helperId"] == KNOWN_USER_NOT_IN_HELPERS.user_id
    # プロフィールが分かる利用者は、その表示名と本人確認状態を使う
    assert items[0]["helper"]["displayName"] == "鈴木 雪"
    assert items[0]["helper"]["verificationStatus"] == "unverified"


def test_requester_sees_applicants_unknown_to_every_seed() -> None:
    request_id = create_published_request()
    apply_as(UNKNOWN_USER, request_id)

    response = client.get(f"/requests/{request_id}/applications")

    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    helper = items[0]["helper"]
    assert helper["id"] == UNKNOWN_USER.user_id
    # プロフィールが引けなくても一覧は返し、選択できる
    assert helper["displayName"]
    assert helper["verificationStatus"] == "unverified"
    assert helper["achievementCount"] == 0


def test_seed_helpers_keep_their_rich_summary() -> None:
    request_id = create_published_request()
    apply_as(
        CurrentUser(user_id="usr_207", role="member", status="active",
                    email_verified=True, verification_status="approved"),
        request_id,
    )

    response = client.get(f"/requests/{request_id}/applications")

    assert response.status_code == 200
    helper = response.json()["items"][0]["helper"]
    assert helper["displayName"] == "田中 悠"
    assert helper["skillTags"] == ["犬", "地域清掃"]
    assert helper["achievementCount"] == 12


# --- Postgres の行オブジェクトを模した変換テスト ------------------------------


class RecordLike(dict):
    """asyncpg.Record のように、`in` が列名を見ない前提でも壊れないことを確かめる。"""

    def __contains__(self, item: object) -> bool:  # 値だけを見る（列名では常に False）
        return item in self.values()


BASE_ROW = {
    "id": "1a2b", "request_id": "3c4d", "message": "対応できます",
    "available_at": "2099-09-10T07:00:00+09:00", "status": "applied",
    "created_at": "2026-09-04T10:00:00+00:00", "updated_at": None,
    "helper_auth_subject": UNKNOWN_USER.user_id,
}


def test_row_with_profile_columns_builds_helper_even_if_in_checks_values() -> None:
    row = RecordLike({
        **BASE_ROW,
        "helper_display_name": "山田 太郎", "helper_verification_status": "approved",
        "helper_email_verified": True, "achievement_count": 3,
    })

    record = _row_to_record(row)

    assert record["helper"] == {
        "id": UNKNOWN_USER.user_id, "displayName": "山田 太郎",
        "verificationStatus": "approved", "universityVerified": True,
        "skillTags": [], "achievementCount": 3,
    }


def test_row_with_missing_profile_values_falls_back_safely() -> None:
    row = RecordLike({
        **BASE_ROW,
        "helper_display_name": None, "helper_verification_status": None,
        "helper_email_verified": None, "achievement_count": None,
    })

    record = _row_to_record(row)

    assert record["helper"]["displayName"]
    assert record["helper"]["verificationStatus"] == "unverified"
    assert record["helper"]["universityVerified"] is False
    assert record["helper"]["achievementCount"] == 0


def test_row_without_profile_columns_has_no_helper() -> None:
    record = _row_to_record(RecordLike(BASE_ROW))

    assert "helper" not in record
