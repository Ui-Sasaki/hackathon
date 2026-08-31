import { apiClient, type ApiClient } from "../../api/client";
import { ApiError } from "../../api/errors";
import type { Match } from "../matches/client";

const applicationErrorMessages: Record<string, string> = {
  SELF_APPLICATION_NOT_ALLOWED: "自分の依頼には応募できません。",
  VERIFICATION_REQUIRED: "この依頼への応募には本人確認が必要です。",
  DUPLICATE_APPLICATION: "この依頼には応募済みです。",
  REQUEST_EXPIRED: "この依頼の募集期限は終了しました。",
  REQUEST_NOT_OPEN: "この依頼は現在募集していません。",
};

export function applicationErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return applicationErrorMessages[error.code] ?? error.message;
  }
  return "応募を送信できませんでした。通信環境を確認して、もう一度お試しください。";
}

const withdrawalErrorMessages: Record<string, string> = {
  AUTHENTICATION_REQUIRED: "セッションの有効期限が切れました。もう一度ログインしてください。",
  ROLE_FORBIDDEN: "この応募を取り下げる権限がありません。",
  APPLICATION_NOT_FOUND: "応募が見つかりません。",
  APPLICATION_NOT_WITHDRAWABLE: "この応募はすでに取り下げ済みか、現在の状態では取り下げできません。",
};

const selectionErrorMessages: Record<string, string> = {
  AUTHENTICATION_REQUIRED: "セッションの有効期限が切れました。もう一度ログインしてください。",
  ROLE_FORBIDDEN: "この応募者を選択する権限がありません。",
  APPLICATION_NOT_FOUND: "応募が見つかりません。",
  REQUEST_NOT_FOUND: "依頼が見つかりません。",
  REQUEST_STATE_CONFLICT: "依頼が更新されています。最新の応募者一覧を取得してください。",
  APPLICATION_NOT_SELECTABLE: "この応募は現在選択できません。",
  HELPER_VERIFICATION_REQUIRED: "応募者の本人確認状態が変更されたため選択できません。",
  CAPACITY_REACHED: "募集人数に達しています。",
  APPLICATION_SELECTION_UNAVAILABLE: "現在応募者を選択できません。時間をおいてお試しください。",
};

export function selectionErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return selectionErrorMessages[error.code] ?? error.message;
  }
  return "応募者を選択できませんでした。通信環境を確認して、もう一度お試しください。";
}

export function withdrawalErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return withdrawalErrorMessages[error.code] ?? error.message;
  }
  return "応募を取り下げできませんでした。通信環境を確認して、もう一度お試しください。";
}

export type CreateApplicationInput = {
  message: string;
  availableAt: string;
};

export type ApplicationStatus =
  | "applied"
  | "selected"
  | "accepted"
  | "completed"
  | "not_selected"
  | "withdrawn"
  | "cancelled";

export type Application = {
  id: string;
  requestId: string;
  helperId: string;
  message: string;
  availableAt: string;
  status: ApplicationStatus;
  createdAt: string;
  updatedAt: string | null;
};

export type Applicant = Application & {
  helper: {
    id: string;
    displayName: string;
    verificationStatus: "unverified" | "pending" | "approved" | "rejected" | "expired";
    universityVerified: boolean;
    skillTags: string[];
    achievementCount: number;
  };
};

export type ApplicantListState =
  | { status: "loading"; requestId: string; items: Applicant[]; error: null }
  | { status: "ready"; requestId: string; items: Applicant[]; error: null }
  | { status: "empty"; requestId: string; items: []; error: null }
  | { status: "error"; requestId: string; items: []; error: unknown };

export function applicantListLoadingState(requestId: string): ApplicantListState {
  return { status: "loading", requestId, items: [], error: null };
}

export async function listApplicants(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<ApplicantListState> {
  try {
    const response = await client.get<{ items: Applicant[] }>(
      `/requests/${encodeURIComponent(requestId)}/applications`,
    );
    if (response.items.length === 0) {
      return { status: "empty", requestId, items: [], error: null };
    }
    return { status: "ready", requestId, items: response.items, error: null };
  } catch (error) {
    return { status: "error", requestId, items: [], error };
  }
}

const pendingSelections = new WeakMap<ApiClient, Map<string, Promise<Match>>>();

export function selectApplicant(
  applicationId: string,
  expectedVersion: number,
  client: ApiClient = apiClient,
): Promise<Match> {
  let clientSelections = pendingSelections.get(client);
  if (!clientSelections) {
    clientSelections = new Map();
    pendingSelections.set(client, clientSelections);
  }
  const pending = clientSelections.get(applicationId);
  if (pending) return pending;

  const selection = client
    .post<Match>(`/applications/${encodeURIComponent(applicationId)}/select`, {
      expectedVersion,
    })
    .finally(() => clientSelections?.delete(applicationId));
  clientSelections.set(applicationId, selection);
  return selection;
}

export function createApplication(
  requestId: string,
  input: CreateApplicationInput,
  client: ApiClient = apiClient,
): Promise<Application> {
  return client.post<Application>(
    `/requests/${encodeURIComponent(requestId)}/applications`,
    {
      message: input.message,
      availableAt: input.availableAt,
    },
  );
}

const pendingWithdrawals = new WeakMap<ApiClient, Map<string, Promise<Application>>>();

export function withdrawApplication(
  applicationId: string,
  client: ApiClient = apiClient,
): Promise<Application> {
  let clientWithdrawals = pendingWithdrawals.get(client);
  if (!clientWithdrawals) {
    clientWithdrawals = new Map();
    pendingWithdrawals.set(client, clientWithdrawals);
  }

  const pending = clientWithdrawals.get(applicationId);
  if (pending) return pending;

  const withdrawal = client
    .post<Application>(`/applications/${encodeURIComponent(applicationId)}/withdraw`)
    .finally(() => clientWithdrawals?.delete(applicationId));
  clientWithdrawals.set(applicationId, withdrawal);
  return withdrawal;
}
