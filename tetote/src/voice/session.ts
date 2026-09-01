/**
 * 音声入力の状態遷移。UIから切り離した純粋な関数として持つことで、
 * 権限拒否・取消・再録音・文字修正・送信をブラウザなしで検証できる。
 */

import { maskPersonalInfo, MaskResult } from "./masking";

export type VoiceErrorReason =
  | "unsupported"
  | "permission-denied"
  | "recording-failed"
  | "transcription-failed"
  | "empty-transcript";

export const VOICE_ERROR_MESSAGES: Record<VoiceErrorReason, string> = {
  unsupported: "このブラウザでは音声入力を利用できません。手で入力へ切り替えてください。",
  "permission-denied":
    "マイクの利用が許可されませんでした。ブラウザの設定で許可するか、手で入力へ切り替えてください。",
  "recording-failed":
    "録音できませんでした。マイクが使える状態か確認して、もう一度お試しください。",
  "transcription-failed":
    "文字起こしに失敗しました。もう一度録音するか、手で入力へ切り替えてください。",
  "empty-transcript":
    "音声を聞き取れませんでした。もう一度録音するか、手で入力へ切り替えてください。",
};

export type VoiceState =
  /** 録音前。マイクの利用目的を表示している状態。 */
  | { status: "idle" }
  /** 録音中。停止と取消だけを受け付ける。 */
  | { status: "listening" }
  /** 録音を止めて文字起こしの結果を待っている状態。 */
  | { status: "transcribing" }
  /** 文字起こし結果を編集できる状態。ここではまだ送信しない。 */
  | { status: "review"; draft: string }
  /** 利用者が確認した後の状態。マスク済みテキストはここでしか取り出せない。 */
  | { status: "confirmed"; draft: string; submission: MaskResult }
  /** 失敗した状態。draft には手入力へ引き継げる文字が残る。 */
  | { status: "error"; reason: VoiceErrorReason; draft: string };

export type VoiceAction =
  | { type: "start" }
  | { type: "stop" }
  | { type: "cancel" }
  | { type: "transcribed"; text: string }
  | { type: "edit"; text: string }
  | { type: "confirm" }
  | { type: "fail"; reason: VoiceErrorReason };

export const initialVoiceState: VoiceState = { status: "idle" };

function draftOf(state: VoiceState): string {
  if (state.status === "review" || state.status === "confirmed") {
    return state.draft;
  }

  if (state.status === "error") {
    return state.draft;
  }

  return "";
}

export function voiceReducer(
  state: VoiceState,
  action: VoiceAction,
): VoiceState {
  switch (action.type) {
    case "start":
      // 非対応ブラウザの案内中は録音させない。再録音は他の状態から常に始められる。
      if (state.status === "error" && state.reason === "unsupported") {
        return state;
      }

      return { status: "listening" };

    case "stop":
      return state.status === "listening"
        ? { status: "transcribing" }
        : state;

    case "cancel":
      // 取消は録音も文字起こし結果も破棄する。音声を残さないための既定動作。
      return { status: "idle" };

    case "transcribed": {
      if (state.status !== "transcribing") {
        return state;
      }

      const draft = action.text.trim();

      if (draft.length === 0) {
        return { status: "error", reason: "empty-transcript", draft: "" };
      }

      return { status: "review", draft };
    }

    case "edit":
      // 確認画面から戻って直す場合があるため、確認後の編集も受け付ける。
      return state.status === "review" || state.status === "confirmed"
        ? { status: "review", draft: action.text }
        : state;

    case "confirm": {
      if (state.status !== "review") {
        return state;
      }

      const draft = state.draft.trim();

      if (draft.length === 0) {
        return { status: "error", reason: "empty-transcript", draft: "" };
      }

      // 送信テキストは確認後にここで初めて作られ、必ずマスクを通る。
      return {
        status: "confirmed",
        draft,
        submission: maskPersonalInfo(draft),
      };
    }

    case "fail":
      return {
        status: "error",
        reason: action.reason,
        draft: draftOf(state),
      };

    default:
      return state;
  }
}

/** 確認済みの送信内容を取り出す。未確認の状態では null を返す。 */
export function submissionOf(state: VoiceState): MaskResult | null {
  return state.status === "confirmed" ? state.submission : null;
}

/** 手で入力へ切り替えるときに引き継ぐ文字。 */
export function fallbackTextOf(state: VoiceState): string {
  return draftOf(state);
}
