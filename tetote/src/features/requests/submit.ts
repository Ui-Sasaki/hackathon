import { apiClient, type ApiClient } from "../../api/client";
import { ApiAuthenticationError, ApiError } from "../../api/errors";
import {
  beginRequestCreation,
  submitRequestCreation,
  type CreateRequestInput,
  type CreatedRequest,
} from "../../api/request-creation";
import { publishRequest } from "../../api/request-publish";
import type { StructuredRequestDraft } from "../../api/request-structuring";

/**
 * 確認画面の下書きを、作成API（POST /requests）へ送れる形に整えて、
 * 作成→公開までを一続きで行う層。
 *
 * AI構造化の結果には日時や所要時間が入らないことがあるため、手入力画面で
 * 選んだ「必要な時間」「いつまで」の表示ラベルから補い、それも無ければ
 * 安全側の既定値を使う。値の妥当性は最終的にサーバーが検証する。
 */

export type ManualRequestInputs = {
  /** 手入力画面の「必要な時間」ラベル（例: "30分以内"）。音声入力では無い。 */
  time?: string;
  /** 手入力画面の「いつまで」ラベル（例: "3日後"）。 */
  deadline?: string;
};

export type BuildRequestInputOptions = {
  now?: Date;
  /** プロフィールなどから分かる地域コード。下書きに地域が無いときに使う。 */
  fallbackAreaCode?: string;
};

export type BuildRequestInputResult =
  | { input: CreateRequestInput; problem: null }
  | { input: null; problem: string };

const MIN_MINUTES = 10;
const MAX_MINUTES = 240;
const DEFAULT_MINUTES = 30;
const DEFAULT_AREA_CODE = "AREA-001";
const DEFAULT_CATEGORY = "other";
const TITLE_MAX_LENGTH = 100;

const minutesByLabel: Record<string, number> = {
  "15分以内": 15,
  "30分以内": 30,
  "30分〜1時間": 60,
  "1時間〜2時間": 120,
  "2時間〜3時間": 180,
  "半日": 240,
  "1日": 240,
};

const daysByDeadline: Record<string, number> = {
  "24時間後": 1,
  "3日後": 3,
  "1週間後": 7,
};

export function estimatedMinutesFromLabel(label: string | undefined): number | null {
  if (!label) return null;
  return minutesByLabel[label] ?? null;
}

export function scheduledAtFromDeadline(label: string | undefined, now: Date = new Date()): string {
  const days = (label && daysByDeadline[label]) || 3;
  const scheduled = new Date(now.getTime() + days * 24 * 60 * 60 * 1000);
  return scheduled.toISOString();
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, Math.round(value)));
}

export function buildCreateRequestInput(
  draft: StructuredRequestDraft,
  inputs: ManualRequestInputs = {},
  options: BuildRequestInputOptions = {},
): BuildRequestInputResult {
  const description = draft.description.trim();
  if (!description) {
    return { input: null, problem: "依頼内容を入力してください。" };
  }

  const title = (draft.title.trim() || description).slice(0, TITLE_MAX_LENGTH);
  const category = draft.category.trim() || DEFAULT_CATEGORY;
  const estimatedMinutes = clamp(
    draft.estimatedMinutes ?? estimatedMinutesFromLabel(inputs.time) ?? DEFAULT_MINUTES,
    MIN_MINUTES,
    MAX_MINUTES,
  );
  const requiredHelpers = clamp(draft.requiredHelpers ?? 1, 1, 5);
  const scheduledAt = draft.scheduledAt ?? scheduledAtFromDeadline(inputs.deadline, options.now);
  const areaCode = draft.approximateArea || options.fallbackAreaCode || DEFAULT_AREA_CODE;

  return {
    input: {
      title,
      description,
      category,
      scheduledAt,
      estimatedMinutes,
      requiredHelpers,
      areaCode,
      // 危険度はサーバーが判定し直す。ここでは送れる2値に寄せるだけ。
      riskLevel: draft.riskLevel === "medium" ? "medium" : "low",
      confirmed: true,
    },
    problem: null,
  };
}

export type RequestSubmissionState =
  | { status: "published"; request: CreatedRequest; error: null }
  | { status: "pending_review"; request: CreatedRequest; error: null }
  | { status: "created_unpublished"; request: CreatedRequest; error: unknown }
  | {
      status: "failed";
      reason: "prohibited" | "validation_error" | "conflict" | "authentication" | "error";
      request: null;
      error: unknown;
    };

/** 依頼を作成し、審査対象でなければそのまま公開する。 */
export async function submitAndPublishRequest(
  input: CreateRequestInput,
  client: ApiClient = apiClient,
  createIdempotencyKey?: () => string,
): Promise<RequestSubmissionState> {
  const attempt = beginRequestCreation(input, createIdempotencyKey);
  const creation = await submitRequestCreation(attempt, client);

  if (creation.status !== "created") {
    return { status: "failed", reason: failureReason(creation.error), request: null, error: creation.error };
  }

  if (creation.request.status === "pending_review") {
    return { status: "pending_review", request: creation.request, error: null };
  }

  const publication = await publishRequest(creation.request.id, client);
  if (publication.status === "published") {
    return { status: "published", request: publication.request, error: null };
  }
  if (publication.status === "under_review") {
    return { status: "pending_review", request: creation.request, error: null };
  }
  return { status: "created_unpublished", request: creation.request, error: publication.error };
}

function failureReason(error: unknown): Extract<RequestSubmissionState, { status: "failed" }>["reason"] {
  if (error instanceof ApiAuthenticationError) return "authentication";
  if (error instanceof ApiError) {
    if (error.code === "PROHIBITED_REQUEST") return "prohibited";
    if (error.status === 422) return "validation_error";
    if (error.status === 409) return "conflict";
  }
  return "error";
}

export function submissionErrorMessage(state: RequestSubmissionState): string | null {
  switch (state.status) {
    case "published":
    case "pending_review":
      return null;
    case "created_unpublished":
      return "依頼は保存されましたが、公開できませんでした。しばらくしてからもう一度お試しください。";
    case "failed":
      switch (state.reason) {
        case "prohibited":
          return "この内容の依頼はお受けできません。内容を見直してください。";
        case "validation_error":
          return "依頼内容を確認して、もう一度お試しください。";
        case "conflict":
          return "同じ依頼を処理中です。少し待ってから画面を更新してください。";
        case "authentication":
          return "セッションの有効期限が切れました。もう一度ログインしてください。";
        default:
          return "依頼を送信できませんでした。通信環境を確認して、もう一度お試しください。";
      }
  }
}
