"""固定ルールとLLMを併用した危険度判定のテスト。"""

import asyncio
import os

os.environ["SUPERTOKENS_ENABLED"] = "false"
os.environ["MOCK_RESET_ENABLED"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["REQUEST_REPOSITORY"] = "memory"

import httpx
import pytest

import app.cruds.main as crud_module
from app.auth import CurrentUser, get_current_user
from app.main import app
from app.services import safety


class ASGITestClient:
    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as async_client:
                return await async_client.request(method, path, **kwargs)

        return asyncio.run(send())

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def patch(self, path: str, **kwargs) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)


client = ASGITestClient()

REQUESTER = CurrentUser(
    user_id="usr_101",
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
    crud_module.configure_safety_llm_client(safety.default_safety_llm_client)


def assess(text: str, **kwargs) -> safety.RiskAssessment:
    return asyncio.run(safety.assess_risk(text, **kwargs))


def llm_returning(**payload):
    async def client_fn(masked_text: str) -> dict:
        del masked_text
        return payload

    return client_fn


async def llm_unavailable(masked_text: str) -> dict:
    del masked_text
    raise RuntimeError("safety model timed out")


def create_payload(**overrides) -> dict:
    payload = {
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
    payload.update(overrides)
    return payload


# --- 固定ルール ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("父の介護を手伝ってほしい", "PROHIBITED_MEDICAL_CARE"),
        ("コンセント増設をお願いしたい", "PROHIBITED_ELECTRICAL_WORK"),
        ("屋根の上の掃除をお願いしたい", "PROHIBITED_HEIGHT_WORK"),
        ("チェーンソーで木を切ってほしい", "PROHIBITED_DANGEROUS_TOOL"),
        ("通帳を預かって記帳してきてほしい", "PROHIBITED_MONEY_HANDLING"),
        ("病院まで車で送ってほしい", "PROHIBITED_TRANSPORT"),
        ("買い物代行をお願いしたい", "PROHIBITED_SHOPPING_PROXY"),
    ],
)
def test_fixed_rules_detect_out_of_scope_work(text: str, code: str) -> None:
    assessment = assess(text)
    assert assessment.level == "prohibited"
    assert assessment.decision == "rejected"
    assert code in assessment.reason_codes


def test_ordinary_request_is_publishable() -> None:
    assessment = assess("庭の落ち葉を一緒に片付けてください")
    assert assessment.level == "low"
    assert assessment.decision == "publish"
    assert assessment.reason_codes == ()


def test_full_width_weight_is_normalized_before_matching() -> None:
    assert assess("２０ｋｇの荷物を運んでほしい").level == "high"


# --- 境界値 -------------------------------------------------------------


@pytest.mark.parametrize(
    ("weight", "expected"),
    [("19kg", "low"), ("20kg", "high"), ("21kg", "high"), ("19.9キロ", "low")],
)
def test_weight_boundary_sends_heavy_loads_to_review(weight: str, expected: str) -> None:
    assert assess(f"{weight}の荷物を運ぶのを手伝ってほしい").level == expected


@pytest.mark.parametrize(
    ("hour", "expected"),
    [("21:00", "low"), ("22:00", "high"), ("05:59", "high"), ("06:00", "low")],
)
def test_late_night_boundary_sends_work_to_review(hour: str, expected: str) -> None:
    assessment = assess(
        "荷物の運び出しを手伝ってほしい",
        scheduled_at=f"2026-09-10T{hour}:00+00:00",
    )
    assert assessment.level == expected


def test_unparsable_schedule_does_not_escalate() -> None:
    assert assess("草むしりを手伝ってほしい", scheduled_at="いつでも").level == "low"


# --- 固定ルールとLLMの競合 ---------------------------------------------


def test_llm_cannot_lift_a_fixed_prohibition() -> None:
    assessment = assess(
        "介護を手伝ってほしい", llm_client=llm_returning(riskLevel="low", model="test")
    )
    assert assessment.level == "prohibited"
    assert assessment.decision == "rejected"
    # 禁止が確定した入力はLLMへ渡さない。
    assert assessment.llm_status == "skipped_fixed_rule"
    assert assessment.llm_level is None


def test_llm_cannot_lower_a_fixed_review_level() -> None:
    assessment = assess(
        "冷蔵庫の移動を手伝ってほしい",
        llm_client=llm_returning(riskLevel="low", model="test"),
    )
    assert assessment.level == "high"
    assert assessment.decision == "pending_review"
    assert assessment.llm_level == "low"


def test_llm_can_escalate_a_low_request() -> None:
    assessment = assess(
        "夜間に一人で作業してほしい",
        llm_client=llm_returning(riskLevel="high", reason="夜間の単独作業", model="test"),
    )
    assert assessment.level == "high"
    assert "LLM_FLAGGED" in assessment.reason_codes
    assert "夜間の単独作業" in assessment.messages


def test_llm_alone_cannot_declare_a_prohibition() -> None:
    assessment = assess(
        "本棚の整理を手伝ってほしい",
        llm_client=llm_returning(riskLevel="prohibited", model="test"),
    )
    assert assessment.level == "high"
    assert assessment.decision == "pending_review"


# --- LLM障害 -----------------------------------------------------------


def test_llm_failure_sends_the_request_to_review() -> None:
    assessment = assess("本棚の整理を手伝ってほしい", llm_client=llm_unavailable)
    assert assessment.level == "high"
    assert assessment.decision == "pending_review"
    assert "LLM_UNAVAILABLE" in assessment.reason_codes
    assert assessment.llm_status == "unavailable"


def test_unusable_llm_output_sends_the_request_to_review() -> None:
    assessment = assess(
        "本棚の整理を手伝ってほしい", llm_client=llm_returning(riskLevel="なんとなく危険")
    )
    assert assessment.decision == "pending_review"
    assert "LLM_INVALID_OUTPUT" in assessment.reason_codes


def test_llm_failure_does_not_publish_a_prohibited_request() -> None:
    assessment = assess("電気工事をお願いしたい", llm_client=llm_unavailable)
    assert assessment.decision == "rejected"


# --- 監査 ---------------------------------------------------------------


def test_assessment_records_its_own_evidence() -> None:
    payload = assess(
        "本棚の整理を手伝ってほしい",
        llm_client=llm_returning(riskLevel="medium", model="safety-test-model"),
    ).to_payload()

    assert payload["ruleVersion"] == safety.RULE_VERSION
    assert payload["promptVersion"] == safety.PROMPT_VERSION
    assert payload["model"] == "safety-test-model"
    assert payload["llmLevel"] == "medium"
    assert payload["evaluatedAt"].endswith("Z")


# --- API接続 -----------------------------------------------------------


def test_structure_endpoint_rejects_prohibited_text() -> None:
    response = client.post(
        "/requests/structure",
        json={"text": "電気工事をお願いしたい", "areaCode": "AREA-001"},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "PROHIBITED_REQUEST"
    assert "PROHIBITED_ELECTRICAL_WORK" in error["details"]["reasonCodes"]


def test_structure_endpoint_returns_the_assessment() -> None:
    response = client.post(
        "/requests/structure",
        json={"text": "庭の落ち葉を片付けてほしい 時間は30分 場所は庭", "areaCode": "AREA-001"},
    )
    assert response.status_code == 200
    assessment = response.json()["safety"]
    assert assessment["riskLevel"] == "low"
    assert assessment["decision"] == "publish"
    assert assessment["ruleVersion"] == safety.RULE_VERSION


def test_structure_endpoint_assesses_masked_text_only() -> None:
    seen: list[str] = []

    async def capture(masked_text: str) -> dict:
        seen.append(masked_text)
        return {"riskLevel": "low", "model": "test"}

    crud_module.configure_safety_llm_client(capture)
    response = client.post(
        "/requests/structure",
        json={
            "text": "庭の掃除をお願いしたい。連絡先は 090-1234-5678 です",
            "areaCode": "AREA-001",
            "maskingConfirmed": True,
        },
    )
    assert response.status_code == 200
    assert seen and "090-1234-5678" not in seen[0]
    assert "[電話番号]" in seen[0]


def test_create_request_rejects_prohibited_content() -> None:
    response = client.post(
        "/requests",
        json=create_payload(title="電気工事", description="コンセントを増設してほしい"),
        headers={"Idempotency-Key": "safety-reject-1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PROHIBITED_REQUEST"


def test_create_request_sends_review_targets_to_pending_review() -> None:
    response = client.post(
        "/requests",
        json=create_payload(title="冷蔵庫の移動", description="冷蔵庫を動かすのを手伝ってほしい"),
        headers={"Idempotency-Key": "safety-review-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending_review"
    assert body["riskLevel"] == "high"
    assert body["warnings"]


def test_create_request_publishes_ordinary_requests() -> None:
    response = client.post(
        "/requests",
        json=create_payload(),
        headers={"Idempotency-Key": "safety-ok-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "published"
    assert body["riskLevel"] == "low"


def test_create_request_ignores_the_risk_level_sent_by_the_client() -> None:
    response = client.post(
        "/requests",
        json=create_payload(
            title="冷蔵庫の移動",
            description="冷蔵庫を動かすのを手伝ってほしい",
            riskLevel="low",
        ),
        headers={"Idempotency-Key": "safety-client-claim-1"},
    )
    assert response.status_code == 201
    assert response.json()["riskLevel"] == "high"


_created = 0


def create_request(**overrides) -> dict:
    global _created
    _created += 1
    response = client.post(
        "/requests",
        json=create_payload(**overrides),
        headers={"Idempotency-Key": f"safety-update-{_created}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_update_cannot_smuggle_prohibited_content_past_creation() -> None:
    created = create_request()
    response = client.patch(
        f"/requests/{created['id']}",
        json={
            "description": "やっぱりコンセント増設をお願いしたい",
            "expectedVersion": created["version"],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PROHIBITED_REQUEST"


def test_update_into_review_territory_sends_the_request_to_review() -> None:
    created = create_request(title="荷物の整理")
    response = client.patch(
        f"/requests/{created['id']}",
        json={
            "description": "冷蔵庫を動かすのを手伝ってほしい",
            "expectedVersion": created["version"],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"


def test_update_without_text_changes_keeps_the_current_state() -> None:
    created = create_request(title="本棚の整理")
    response = client.patch(
        f"/requests/{created['id']}",
        json={"estimatedMinutes": 60, "expectedVersion": created["version"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    assert body["estimatedMinutes"] == 60
