"""キャラクター（貢献度）の進捗を、完了済みの支援活動から計算する。

ポイント規則と進化条件は画面側との合意事項なので、この1ファイルに集約する
（`docs/cross-team-coordination.md` COORD-005）。規則を変えるときはここと
フロントの表示だけを直せばよい。集計値はクライアントから受け取らず、常に
サーバーが完了済みマッチから計算する。
"""

from __future__ import annotations

from typing import Any, Iterable, TypedDict

RULE_VERSION = "v1"

# 1回の支援で必ず入るポイント。これに活動時間（分）を足す。
POINTS_PER_HELP = 50

# 各段階が始まるポイント。段階1は0pt、段階2は150pt、段階3は350ptから。
STAGE_THRESHOLDS: tuple[int, ...] = (0, 150, 350)

# 段階ごとの表示キャラクター識別子。tetote/assets/onboarding_asset/c{n}.jpg と対応する。
CHARACTER_IDS: tuple[str, ...] = ("c1", "c2", "c3")


class CompletedHelp(TypedDict):
    matchId: str
    estimatedMinutes: int


def points_for_help(estimated_minutes: int) -> int:
    """1回の完了した支援に付くポイント。"""
    return POINTS_PER_HELP + max(0, int(estimated_minutes))


def stage_for_points(points: int) -> int:
    """ポイントから段階（1始まり）を求める。"""
    stage = 1
    for index, threshold in enumerate(STAGE_THRESHOLDS, start=1):
        if points >= threshold:
            stage = index
    return stage


def build_progress(user_id: str, helps: Iterable[CompletedHelp]) -> dict[str, Any]:
    """完了済み支援の一覧から、画面が表示する進捗をまとめる。"""
    help_list = list(helps)
    points = sum(points_for_help(item["estimatedMinutes"]) for item in help_list)
    stage = stage_for_points(points)
    stage_start = STAGE_THRESHOLDS[stage - 1]
    is_max_stage = stage >= len(STAGE_THRESHOLDS)
    next_stage_points = None if is_max_stage else STAGE_THRESHOLDS[stage]

    if next_stage_points is None:
        points_until_next = 0
        ratio = 1.0
    else:
        points_until_next = max(0, next_stage_points - points)
        span = next_stage_points - stage_start
        ratio = (points - stage_start) / span if span > 0 else 1.0

    return {
        "userId": user_id,
        "helpCount": len(help_list),
        "currentPoints": points,
        "stage": stage,
        "maxStage": len(STAGE_THRESHOLDS),
        "characterId": CHARACTER_IDS[stage - 1],
        "nextStagePoints": next_stage_points,
        "pointsUntilNextStage": points_until_next,
        "progressRatio": round(min(1.0, max(0.0, ratio)), 3),
        "ruleVersion": RULE_VERSION,
    }
