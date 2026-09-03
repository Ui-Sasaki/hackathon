"""キャラクター進捗APIのテスト。完了済みマッチだけを集計することを確かめる。"""

import asyncio
import os

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["REQUEST_REPOSITORY"] = "memory"

import httpx

import app.cruds.main as crud_module
from app.auth import CurrentUser, get_current_user
from app.cruds.main import SEED_REQUEST_1024, SEED_REQUEST_1025
from app.main import app
from app.services import character


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

HELPER = CurrentUser(
    user_id="usr_207", role="member", status="active",
    email_verified=True, verification_status="approved",
)
OTHER_HELPER = CurrentUser(
    user_id="usr_208", role="member", status="active",
    email_verified=True, verification_status="unverified",
)


def act_as(user: CurrentUser) -> None:
    async def current() -> CurrentUser:
        return user

    app.dependency_overrides[get_current_user] = current


def setup_function() -> None:
    act_as(HELPER)
    client.post("/_mock/reset")


def seed_match(match_id: str, *, helper_id: str, request_id: str, status: str) -> None:
    """API本体が使っている辞書へ直接マッチを置く（マッチ作成APIを経由しない）。"""
    crud_module.matches[match_id] = {
        "id": match_id,
        "requestId": request_id,
        "requesterId": "usr_101",
        "helperId": helper_id,
        "status": status,
        "requesterConfirmed": status == "completed",
        "helperConfirmed": status == "completed",
        "matchedAt": "2026-09-01T10:00:00Z",
        "completedAt": "2026-09-02T10:00:00Z" if status == "completed" else None,
        "version": 1,
    }


# --- 規則そのもの ------------------------------------------------------------


def test_points_add_a_fixed_bonus_to_the_activity_minutes() -> None:
    assert character.points_for_help(30) == 80
    assert character.points_for_help(0) == 50
    assert character.points_for_help(-10) == 50


def test_stage_boundaries_follow_the_thresholds() -> None:
    assert character.stage_for_points(0) == 1
    assert character.stage_for_points(149) == 1
    assert character.stage_for_points(150) == 2
    assert character.stage_for_points(349) == 2
    assert character.stage_for_points(350) == 3
    assert character.stage_for_points(10_000) == 3


def test_final_stage_has_no_next_target() -> None:
    progress = character.build_progress(
        "usr_x", [{"matchId": "m", "estimatedMinutes": 300}] * 2,
    )
    assert progress["stage"] == 3
    assert progress["characterId"] == "c3"
    assert progress["nextStagePoints"] is None
    assert progress["pointsUntilNextStage"] == 0
    assert progress["progressRatio"] == 1.0


# --- API -------------------------------------------------------------------


def test_new_helper_starts_at_stage_one_with_nothing() -> None:
    response = client.get("/character-progress")

    assert response.status_code == 200
    assert response.json() == {
        "userId": HELPER.user_id,
        "helpCount": 0,
        "currentPoints": 0,
        "stage": 1,
        "maxStage": 3,
        "characterId": "c1",
        "nextStagePoints": 150,
        "pointsUntilNextStage": 150,
        "progressRatio": 0.0,
        "ruleVersion": character.RULE_VERSION,
    }


def test_only_completed_matches_of_the_helper_count() -> None:
    seed_match("m_done", helper_id=HELPER.user_id, request_id=SEED_REQUEST_1024, status="completed")
    seed_match("m_pending", helper_id=HELPER.user_id, request_id=SEED_REQUEST_1025, status="completion_pending")
    seed_match("m_matched", helper_id=HELPER.user_id, request_id=SEED_REQUEST_1025, status="matched")
    seed_match("m_disputed", helper_id=HELPER.user_id, request_id=SEED_REQUEST_1025, status="disputed")
    seed_match("m_other", helper_id=OTHER_HELPER.user_id, request_id=SEED_REQUEST_1025, status="completed")

    response = client.get("/character-progress")

    assert response.status_code == 200
    body = response.json()
    # 種データ 1024 は 30分 → 50 + 30 = 80pt
    assert body["helpCount"] == 1
    assert body["currentPoints"] == 80
    assert body["stage"] == 1
    assert body["characterId"] == "c1"
    assert body["pointsUntilNextStage"] == 70


def test_each_helper_sees_only_their_own_progress() -> None:
    seed_match("m_a", helper_id=HELPER.user_id, request_id=SEED_REQUEST_1024, status="completed")
    seed_match("m_b", helper_id=OTHER_HELPER.user_id, request_id=SEED_REQUEST_1025, status="completed")

    act_as(OTHER_HELPER)
    response = client.get("/character-progress")

    assert response.status_code == 200
    body = response.json()
    assert body["userId"] == OTHER_HELPER.user_id
    assert body["helpCount"] == 1
    # 種データ 1025 は 45分 → 95pt
    assert body["currentPoints"] == 95


def test_reaching_the_threshold_evolves_the_character() -> None:
    seed_match("m_1", helper_id=HELPER.user_id, request_id=SEED_REQUEST_1024, status="completed")
    seed_match("m_2", helper_id=HELPER.user_id, request_id=SEED_REQUEST_1025, status="completed")

    response = client.get("/character-progress")

    body = response.json()
    assert body["helpCount"] == 2
    assert body["currentPoints"] == 175  # 80 + 95
    assert body["stage"] == 2
    assert body["characterId"] == "c2"
    assert body["nextStagePoints"] == 350
    assert body["pointsUntilNextStage"] == 175
    assert body["progressRatio"] == 0.125  # (175 - 150) / (350 - 150)


def test_missing_request_still_counts_the_help_without_minutes() -> None:
    seed_match("m_gone", helper_id=HELPER.user_id, request_id="request-that-was-deleted", status="completed")

    response = client.get("/character-progress")

    body = response.json()
    assert body["helpCount"] == 1
    assert body["currentPoints"] == character.POINTS_PER_HELP


def test_progress_resets_with_the_mock_data() -> None:
    seed_match("m_1", helper_id=HELPER.user_id, request_id=SEED_REQUEST_1024, status="completed")
    assert client.get("/character-progress").json()["helpCount"] == 1

    client.post("/_mock/reset")

    assert client.get("/character-progress").json()["helpCount"] == 0
