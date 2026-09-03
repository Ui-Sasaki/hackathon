import { apiClient, type ApiClient } from "../../api/client";
import { ApiAuthenticationError } from "../../api/errors";

/**
 * キャラクター画面の貢献度をAPIから取得する層。
 * ポイントや段階の計算はサーバーが行う（app/services/character.py）。
 * 画面はここが返す値を表示するだけで、規則を知らなくてよい。
 */

export type CharacterProgress = {
  userId: string;
  helpCount: number;
  currentPoints: number;
  stage: number;
  maxStage: number;
  characterId: string;
  nextStagePoints: number | null;
  pointsUntilNextStage: number;
  progressRatio: number;
  ruleVersion: string;
};

export type CharacterProgressState =
  | { status: "loading"; progress: null; error: null }
  | { status: "ready"; progress: CharacterProgress; error: null }
  | { status: "error"; progress: null; error: unknown };

export function characterProgressLoadingState(): CharacterProgressState {
  return { status: "loading", progress: null, error: null };
}

export async function getCharacterProgress(
  client: ApiClient = apiClient,
): Promise<CharacterProgressState> {
  try {
    const progress = await client.get<CharacterProgress>("/character-progress");
    return { status: "ready", progress, error: null };
  } catch (error) {
    return { status: "error", progress: null, error };
  }
}

export function characterProgressErrorMessage(error: unknown): string {
  if (error instanceof ApiAuthenticationError) {
    return "セッションの有効期限が切れました。もう一度ログインしてください。";
  }
  return "貢献度を読み込めませんでした。通信環境を確認してください。";
}

/** 進捗バーの幅に使う割合（0〜100の整数）。 */
export function progressPercent(progress: CharacterProgress | null): number {
  if (!progress) return 0;
  return Math.round(Math.min(1, Math.max(0, progress.progressRatio)) * 100);
}

/** 「進化まであと◯pt」の文言。最終段階なら進化済みと伝える。 */
export function evolutionLabel(progress: CharacterProgress | null): string {
  if (!progress) return "進化まであと…pt";
  if (progress.nextStagePoints === null) return "最終段階まで進化しました";
  return `進化まであと${progress.pointsUntilNextStage}pt`;
}

export type CharacterAssetKey = "c1" | "c2" | "c3";

const knownAssetKeys: readonly CharacterAssetKey[] = ["c1", "c2", "c3"];

/**
 * サーバーが返す識別子を、画面が持つ画像の鍵に寄せる。
 * 未知の識別子（規則の版が進んだときなど）は最初の姿へ倒し、画面を壊さない。
 * 画像そのもの（require）は画面側が持つ。テストや他画面がこの層を読むときに
 * 画像ファイルの読み込みを要求しないため。
 */
export function characterAssetKey(characterId: string | null | undefined): CharacterAssetKey {
  return knownAssetKeys.find((key) => key === characterId) ?? "c1";
}
