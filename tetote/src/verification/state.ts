/**
 * 本人確認申請の画面状態。UIから切り離した純粋な関数として持ち、
 * 送信中・失敗・再試行・申請済みをブラウザなしで検証できるようにする。
 */

import { ApiError, ApiNetworkError } from "../api/errors";
import { VerificationMethod, VerificationStatus } from "./client";

export type SubmissionState =
  /** 未送信。入力を受け付ける。 */
  | { status: "idle" }
  /** 画像を送っている最中。 */
  | { status: "uploading" }
  /** 申請を送っている最中。 */
  | { status: "submitting" }
  /** 申請が受理された。 */
  | { status: "submitted" }
  /** 失敗した。理由コードと利用者向けメッセージを保持する。 */
  | { status: "error"; code: string; message: string };

export type SubmissionAction =
  | { type: "upload_started" }
  | { type: "upload_finished" }
  | { type: "succeeded" }
  | { type: "failed"; code: string; message: string }
  | { type: "retry" };

export const initialSubmissionState: SubmissionState = { status: "idle" };

export function submissionReducer(
  state: SubmissionState,
  action: SubmissionAction,
): SubmissionState {
  switch (action.type) {
    case "upload_started":
      // 送信中の二重発火は無視する。申請が重複しないようにするための一次防止。
      return state.status === "uploading" || state.status === "submitting"
        ? state
        : { status: "uploading" };

    case "upload_finished":
      return state.status === "uploading" ? { status: "submitting" } : state;

    case "succeeded":
      return { status: "submitted" };

    case "failed":
      return { status: "error", code: action.code, message: action.message };

    case "retry":
      return state.status === "error" ? { status: "idle" } : state;

    default:
      return state;
  }
}

export function isBusy(state: SubmissionState): boolean {
  return state.status === "uploading" || state.status === "submitting";
}

/**
 * 送信できるかを判定する。審査中の重複申請をここで止める。
 */
export function canSubmit(input: {
  state: SubmissionState;
  verificationStatus: VerificationStatus;
  method: VerificationMethod;
  hasDocument: boolean;
}): boolean {
  if (isBusy(input.state) || input.state.status === "submitted") {
    return false;
  }
  // 審査中と承認済みは申請し直せない。
  if (input.verificationStatus === "pending" || input.verificationStatus === "approved") {
    return false;
  }
  if (input.method === "student_card" && !input.hasDocument) {
    return false;
  }
  return true;
}

const MESSAGES: Record<string, string> = {
  VERIFICATION_ALREADY_PENDING: "すでに審査中の申請があります。結果をお待ちください",
  UPLOAD_REQUIRED: "学生証の画像を選んでください",
  UPLOAD_NOT_FOUND: "画像を送り直してください",
  UPLOAD_EXPIRED: "時間が経ちすぎました。画像を選び直してください",
  UPLOAD_ALREADY_USED: "この画像はすでに申請に使われています。選び直してください",
  UPLOAD_CONTENT_MISSING: "画像を送れませんでした。もう一度お試しください",
  UPLOAD_PURPOSE_MISMATCH: "画像を選び直してください",
  IMAGE_TOO_LARGE: "画像は10MBまでにしてください",
  UNSUPPORTED_MEDIA_TYPE: "JPEGまたはPNGの画像を選んでください",
  CONTENT_TYPE_MISMATCH: "画像を読み取れませんでした。別の画像を選んでください",
  EXTENSION_MISMATCH: "画像を読み取れませんでした。別の画像を選んでください",
  INVALID_IMAGE: "画像を読み取れませんでした。別の画像を選んでください",
};

const STATUS_MESSAGES: Record<number, string> = {
  401: "ログインの有効期限が切れました。もう一度ログインしてください",
  403: "この操作を行う権限がありません",
  409: "状態が変わっています。画面を開き直してください",
  413: "画像は10MBまでにしてください",
  415: "JPEGまたはPNGの画像を選んでください",
  422: "入力内容を確認してください",
};

/**
 * 例外を、画面へ出せる理由コードとメッセージへ変換する。
 * サーバーのメッセージをそのまま流さず、既知のコードは画面側の文言に寄せる。
 */
export function describeFailure(error: unknown): { code: string; message: string } {
  if (error instanceof ApiNetworkError) {
    return {
      code: "NETWORK_ERROR",
      message: "通信できませんでした。電波の良い場所でもう一度お試しください",
    };
  }
  if (error instanceof ApiError) {
    const message =
      MESSAGES[error.code] ??
      STATUS_MESSAGES[error.status] ??
      "申請できませんでした。もう一度お試しください";
    return { code: error.code, message };
  }
  return {
    code: "UNKNOWN_ERROR",
    message: "申請できませんでした。もう一度お試しください",
  };
}
