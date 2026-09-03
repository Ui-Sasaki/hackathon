"""Fixed-rule and LLM combined risk assessment for request text.

要件定義書 11.2 と Issue #30 に対応する。固定ルールを常にLLMより優先し、
LLMの判定だけで禁止を解除できない構造にしている。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal

logger = logging.getLogger(__name__)

RULE_VERSION = "safety-rules-v1"
PROMPT_VERSION = "safety-llm-v1"

RiskLevel = Literal["low", "medium", "high", "prohibited"]
Decision = Literal["publish", "publish_with_warning", "pending_review", "rejected"]
LLMStatus = Literal["ok", "skipped_fixed_rule", "skipped_not_configured", "unavailable", "invalid_output"]

# 危険度の強さ。固定ルールとLLMの判定を突き合わせるときに、常に強い方を採用する。
_SEVERITY: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "prohibited": 3}

_DECISIONS: dict[RiskLevel, Decision] = {
    "low": "publish",
    "medium": "publish_with_warning",
    "high": "pending_review",
    "prohibited": "rejected",
}

# 深夜帯の境界。22時から翌6時までを審査対象とする。
LATE_NIGHT_FROM_HOUR = 22
LATE_NIGHT_UNTIL_HOUR = 6

# 一人で扱う上限として審査対象にする重量。
HEAVY_WEIGHT_KG = 20


@dataclass(frozen=True)
class FixedRule:
    code: str
    level: RiskLevel
    message: str
    keywords: tuple[str, ...]


# 要件定義書 3.4「MVP対象外」を禁止として、11.2 が挙げる検査観点を審査対象として並べる。
FIXED_RULES: tuple[FixedRule, ...] = (
    FixedRule(
        "PROHIBITED_MEDICAL_CARE", "prohibited", "医療・介護にあたる作業は依頼できません",
        ("医療行為", "介護", "看護", "服薬", "投薬", "点滴", "注射", "痰の吸引",
         "おむつ交換", "入浴介助", "褥瘡", "喀痰"),
    ),
    FixedRule(
        "PROHIBITED_ELECTRICAL_WORK", "prohibited", "電気工事にあたる作業は依頼できません",
        ("電気工事", "配線工事", "ブレーカー交換", "コンセント増設", "分電盤", "感電"),
    ),
    FixedRule(
        "PROHIBITED_HEIGHT_WORK", "prohibited", "高所での作業は依頼できません",
        ("高所", "屋根", "はしご", "梯子", "脚立", "二階の窓の外", "2階の窓の外", "ベランダの外"),
    ),
    FixedRule(
        "PROHIBITED_DANGEROUS_TOOL", "prohibited", "危険な工具を使う作業は依頼できません",
        ("チェーンソー", "電動のこぎり", "電動ノコギリ", "草刈り機", "刈払機",
         "グラインダー", "溶接", "高圧洗浄機"),
    ),
    FixedRule(
        "PROHIBITED_MONEY_HANDLING", "prohibited", "金銭の管理を伴う依頼はできません",
        ("金銭管理", "通帳", "暗証番号", "キャッシュカード", "振込", "振り込み",
         "現金を預か", "お金を預か", "立て替え"),
    ),
    FixedRule(
        "PROHIBITED_TRANSPORT", "prohibited", "送迎にあたる依頼はできません",
        ("送迎", "車で送", "車に乗せ", "運転して", "送り迎え"),
    ),
    FixedRule(
        "PROHIBITED_SHOPPING_PROXY", "prohibited", "買い物代行にあたる依頼はできません",
        ("買い物代行", "買い物を代わり", "代わりに買ってき", "代理で購入"),
    ),
    FixedRule(
        "REVIEW_LICENSE_REQUIRED", "high", "資格が必要な作業の可能性があります",
        ("有資格", "資格が必要", "施工", "解体", "修理業", "配管工事", "ガス工事"),
    ),
    FixedRule(
        "REVIEW_HEAVY_LIFTING", "high", "重量物の運搬が含まれる可能性があります",
        ("冷蔵庫", "洗濯機", "タンス", "ピアノ", "重い家具", "家具の運搬"),
    ),
    FixedRule(
        "REVIEW_LATE_NIGHT", "high", "深夜帯の作業が含まれる可能性があります",
        ("深夜", "夜中", "未明", "明け方"),
    ),
)

# 「20kg」「20キロ」のような重量表現。半角へ正規化してから数値を取り出す。
_WEIGHT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kg|ｋｇ|キロ|キログラム)")


@dataclass(frozen=True)
class RuleHit:
    code: str
    level: RiskLevel
    message: str


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    decision: Decision
    reason_codes: tuple[str, ...]
    messages: tuple[str, ...]
    llm_level: RiskLevel | None
    llm_status: LLMStatus
    model: str | None
    evaluated_at: str
    fixed_rule_codes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def rejected(self) -> bool:
        return self.decision == "rejected"

    @property
    def needs_review(self) -> bool:
        return self.decision == "pending_review"

    def to_payload(self) -> dict[str, Any]:
        """監査に必要な判定根拠を含めてAPIレスポンスへ載せる形へ変換する。"""
        return {
            "riskLevel": self.level,
            "decision": self.decision,
            "reasonCodes": list(self.reason_codes),
            "messages": list(self.messages),
            "matchedRules": list(self.fixed_rule_codes),
            "ruleVersion": RULE_VERSION,
            "promptVersion": PROMPT_VERSION,
            "model": self.model,
            "llmLevel": self.llm_level,
            "llmStatus": self.llm_status,
            "evaluatedAt": self.evaluated_at,
        }


def _normalize(text: str) -> str:
    """全角英数字を半角へ寄せ、キーワード照合の取りこぼしを減らす。"""
    return "".join(
        chr(ord(char) - 0xFEE0) if "０" <= char <= "９" or "Ａ" <= char <= "ｚ" else char
        for char in text
    ).lower()


def _late_night(scheduled_at: str | None) -> bool:
    if not scheduled_at:
        return False
    try:
        moment = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except ValueError:
        # 形式検証は入力スキーマの責務。ここでは判定できないものを危険側に倒さない。
        return False
    hour = moment.hour
    return hour >= LATE_NIGHT_FROM_HOUR or hour < LATE_NIGHT_UNTIL_HOUR


def _heavy_weight(normalized: str) -> bool:
    return any(
        float(value) >= HEAVY_WEIGHT_KG for value in _WEIGHT_PATTERN.findall(normalized)
    )


def evaluate_fixed_rules(
    text: str, *, scheduled_at: str | None = None
) -> tuple[RuleHit, ...]:
    """固定ルールだけで判定する。LLMを呼ばずに完結し、同じ入力へは常に同じ結果を返す。"""
    normalized = _normalize(text)
    hits = [
        RuleHit(rule.code, rule.level, rule.message)
        for rule in FIXED_RULES
        if any(_normalize(keyword) in normalized for keyword in rule.keywords)
    ]
    if _heavy_weight(normalized) and all(
        hit.code != "REVIEW_HEAVY_LIFTING" for hit in hits
    ):
        hits.append(
            RuleHit("REVIEW_HEAVY_LIFTING", "high", "重量物の運搬が含まれる可能性があります")
        )
    if _late_night(scheduled_at) and all(
        hit.code != "REVIEW_LATE_NIGHT" for hit in hits
    ):
        hits.append(
            RuleHit("REVIEW_LATE_NIGHT", "high", "深夜帯の作業が含まれる可能性があります")
        )
    return tuple(hits)


def _strongest(levels: tuple[RiskLevel, ...]) -> RiskLevel:
    return max(levels, key=lambda level: _SEVERITY[level])


SafetyLLMClient = Callable[[str], Awaitable[dict[str, Any]]]


async def default_safety_llm_client(masked_text: str) -> dict[str, Any]:
    """LLM未設定の開発環境向けの既定実装。判定を行わないことを呼び出し側へ伝える。"""
    del masked_text
    return {"configured": False}


def _read_llm_level(result: dict[str, Any]) -> tuple[RiskLevel | None, LLMStatus, str | None]:
    if result.get("configured") is False:
        return None, "skipped_not_configured", None
    level = result.get("riskLevel")
    if level not in _SEVERITY:
        logger.warning("Safety LLM returned an unusable risk level")
        return None, "invalid_output", result.get("model")
    # LLMが単独で禁止を宣言しても、固定ルールの領域は動かさない。
    if level == "prohibited":
        level = "high"
    return level, "ok", result.get("model")


async def assess_risk(
    masked_text: str,
    *,
    llm_client: SafetyLLMClient = default_safety_llm_client,
    scheduled_at: str | None = None,
) -> RiskAssessment:
    """マスク済みテキストへ固定ルールとLLMを併用した危険度判定を行う。

    `masked_text` は個人情報マスク後の文字列であることを前提とする。
    LLMへ渡すのはこの引数だけで、元の入力は渡さない。
    """
    evaluated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    hits = evaluate_fixed_rules(masked_text, scheduled_at=scheduled_at)
    fixed_level: RiskLevel = _strongest(
        tuple(hit.level for hit in hits) or ("low",)
    )

    # 禁止が確定した入力はLLMへ渡さない。判定を覆す余地を作らないための順序である。
    if fixed_level == "prohibited":
        return RiskAssessment(
            level="prohibited",
            decision=_DECISIONS["prohibited"],
            reason_codes=tuple(hit.code for hit in hits),
            messages=tuple(hit.message for hit in hits),
            llm_level=None,
            llm_status="skipped_fixed_rule",
            model=None,
            evaluated_at=evaluated_at,
            fixed_rule_codes=tuple(hit.code for hit in hits),
        )

    try:
        result = await llm_client(masked_text)
    except Exception:
        # 判断不能は安全側へ倒し、管理者審査へ送る。
        logger.warning("Safety assessment LLM is unavailable")
        result = {}
        llm_level, llm_status, model = None, "unavailable", None
    else:
        llm_level, llm_status, model = _read_llm_level(result)

    reason_codes = [hit.code for hit in hits]
    messages = [hit.message for hit in hits]

    if llm_status in {"unavailable", "invalid_output"}:
        level = _strongest((fixed_level, "high"))
        reason_codes.append(
            "LLM_UNAVAILABLE" if llm_status == "unavailable" else "LLM_INVALID_OUTPUT"
        )
        messages.append("自動判定を完了できなかったため確認が必要です")
    else:
        level = _strongest((fixed_level, llm_level or "low"))
        if llm_level is not None and _SEVERITY[llm_level] > _SEVERITY[fixed_level]:
            reason_codes.append("LLM_FLAGGED")
            reason = result.get("reason")
            messages.append(reason if isinstance(reason, str) and reason else "AI判定により確認が必要です")

    return RiskAssessment(
        level=level,
        decision=_DECISIONS[level],
        reason_codes=tuple(reason_codes),
        messages=tuple(messages),
        llm_level=llm_level,
        llm_status=llm_status,
        model=model,
        evaluated_at=evaluated_at,
        fixed_rule_codes=tuple(hit.code for hit in hits),
    )
