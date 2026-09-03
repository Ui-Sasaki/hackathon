/**
 * 音声入力の会話ループ。確認済みのテキストをバックエンドの構造化APIへ渡し、
 * 不足情報があれば追加質問を1問だけ受け取る。
 *
 * この層は「次に質問するか、確認画面へ進むか」だけを決める。
 * 公開可否を決める正式な構造化・危険度判定は確認画面側で改めて行われるため、
 * ここでの失敗は全て「確認画面へ進む」へ倒す。音声だけが行き止まりにならないようにする。
 */

import { apiClient, type ApiClient } from "../api/client";
import {
  confirmMaskingPreview,
  previewRequestMasking,
} from "../api/request-masking";
import { structureConfirmedRequest } from "../api/request-structuring";

/** 追加質問を繰り返す上限。これを超えたら不足のまま確認画面へ進む。 */
export const MAX_QUESTION_ROUNDS = 2;

export type ConversationStep =
  /** 不足情報があり、利用者へ1問だけ追加質問する。 */
  | { type: "question"; question: string }
  /** 確認画面へ進む。理由は問わない（完了・上限到達・判定不能のいずれも）。 */
  | { type: "proceed" };

/**
 * 確認済みテキストへの次の一手を決める。
 *
 * @param text 利用者が確認した（クライアント側マスク済みの）テキスト
 * @param round これまでに質問へ答えた回数
 */
export async function nextConversationStep(
  text: string,
  round: number,
  client: ApiClient = apiClient,
): Promise<ConversationStep> {
  if (round >= MAX_QUESTION_ROUNDS) {
    return { type: "proceed" };
  }

  // サーバー側のマスキングを通してから構造化へ渡す。マスク結果は利用者が
  // 音声画面で既に確認しているため、ここでは同じ内容の再確認を求めない。
  const preview = await previewRequestMasking(text, client);
  if (preview.status !== "ready") {
    return { type: "proceed" };
  }

  const structured = await structureConfirmedRequest(
    confirmMaskingPreview(preview),
    client,
  );
  if (structured.status === "draft" && structured.additionalQuestion) {
    return { type: "question", question: structured.additionalQuestion };
  }

  // draft（不足なし）、manual（LLM停止時の手動フォールバック）、error のいずれも
  // 確認画面が正式な経路として扱えるため、ここでは止めない。
  return { type: "proceed" };
}

/** 質問への回答を、これまでのテキストへ読める形で継ぎ足す。 */
export function appendAnswer(baseText: string, answer: string): string {
  const trimmed = answer.trim();
  if (!trimmed) return baseText;
  return baseText ? `${baseText}\n${trimmed}` : trimmed;
}
