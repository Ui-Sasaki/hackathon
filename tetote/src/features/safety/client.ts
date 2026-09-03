import { apiClient, type ApiClient } from "../../api/client";
import { ApiError, ApiNetworkError } from "../../api/errors";

/**
 * 通報・ブロックのAPI接続。
 * 送るのは対象・理由・説明だけで、通報者ID・重大度・状態・日時はサーバーが決める。
 */

export type ReportTargetType = "user" | "request" | "match" | "message" | "review";

export type ReportReason =
  | "fraud"
  | "harassment"
  | "dangerous_work"
  | "false_information"
  | "no_show"
  | "personal_information_request"
  | "payment_request"
  | "other";

export const REPORT_REASONS: { value: ReportReason; label: string }[] = [
  { value: "dangerous_work", label: "危険な作業を頼まれた" },
  { value: "fraud", label: "詐欺・金銭トラブルの疑い" },
  { value: "harassment", label: "嫌がらせ・不快な言動" },
  { value: "personal_information_request", label: "個人情報を聞き出そうとした" },
  { value: "payment_request", label: "お金や報酬を要求された" },
  { value: "false_information", label: "内容が事実と違う" },
  { value: "no_show", label: "約束の場所・時間に来なかった" },
  { value: "other", label: "その他" },
];

export const REPORT_DESCRIPTION_MIN = 10;
export const REPORT_DESCRIPTION_MAX = 2000;

export type ReportInput = {
  targetType: ReportTargetType;
  targetId: string;
  reason: ReportReason;
  description: string;
};

export type Report = {
  id: string;
  targetType: ReportTargetType;
  targetId: string;
  reason: string;
  severity: "medium" | "high";
  status: "open" | "resolved";
  createdAt: string;
};

export type BlockResult = {
  userId: string;
  blocked: boolean;
  updatedAt: string;
};

/** 送信前の入力検証。サーバーの制約（10〜2000文字）と同じ条件で早めに止める。 */
export function validateReport(input: {
  reason: ReportReason | null;
  description: string;
}): string | null {
  if (!input.reason) return "理由を選んでください";
  const length = input.description.trim().length;
  if (length < REPORT_DESCRIPTION_MIN) {
    return `状況を${REPORT_DESCRIPTION_MIN}文字以上で書いてください`;
  }
  if (length > REPORT_DESCRIPTION_MAX) {
    return `説明は${REPORT_DESCRIPTION_MAX}文字までです`;
  }
  return null;
}

export async function submitReport(
  input: ReportInput,
  client: ApiClient = apiClient,
): Promise<Report> {
  // 通報者はセッションから決まる。ここで余計な項目を混ぜない。
  return client.post<Report>("/reports", {
    targetType: input.targetType,
    targetId: input.targetId,
    reason: input.reason,
    description: input.description.trim(),
  });
}

export async function setUserBlocked(
  userId: string,
  blocked: boolean,
  client: ApiClient = apiClient,
): Promise<BlockResult> {
  return client.post<BlockResult>(`/users/${encodeURIComponent(userId)}/block`, {
    blocked,
  });
}

/** 通報画面から依頼者をブロックするために、依頼の所有者IDだけを取り出す。 */
export async function fetchRequestOwner(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<string> {
  const request = await client.get<{ requesterId: string }>(
    `/requests/${encodeURIComponent(requestId)}`,
  );
  return request.requesterId;
}

const messages: Record<string, string> = {
  SELF_BLOCK_NOT_ALLOWED: "自分自身はブロックできません",
  USER_PROFILE_NOT_FOUND: "相手の利用者が見つかりませんでした",
  REQUEST_NOT_FOUND: "対象の依頼が見つかりませんでした",
  AUTHENTICATION_REQUIRED: "ログインの有効期限が切れました。もう一度ログインしてください",
  ROLE_FORBIDDEN: "この操作を行う権限がありません",
  VALIDATION_ERROR: "入力内容を確認してください",
};

const statusMessages: Record<number, string> = {
  401: "ログインの有効期限が切れました。もう一度ログインしてください",
  403: "この操作を行う権限がありません",
  404: "対象が見つかりませんでした",
  409: "状態が変わっています。画面を開き直してください",
  422: "入力内容を確認してください",
};

/** 401/403/404/409/422/通信失敗を、画面へ出せる一文へ揃える。 */
export function safetyErrorMessage(error: unknown): string {
  if (error instanceof ApiNetworkError) {
    return "通信できませんでした。電波の良い場所でもう一度お試しください";
  }
  if (error instanceof ApiError) {
    return (
      messages[error.code] ??
      statusMessages[error.status] ??
      "送信できませんでした。もう一度お試しください"
    );
  }
  return "送信できませんでした。もう一度お試しください";
}
