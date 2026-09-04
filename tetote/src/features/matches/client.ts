import { apiClient, type ApiClient } from "../../api/client";
import { ApiError } from "../../api/errors";

export type Match = {
  id: string;
  requestId: string;
  requesterId: string;
  helperId: string;
  status: "matched" | "in_progress" | "completion_pending" | "completed" | "disputed";
  requesterConfirmed: boolean;
  helperConfirmed: boolean;
  matchedAt: string;
  completedAt: string | null;
  disputeReason: string | null;
  disputedAt: string | null;
  version: number;
};

export type MatchDetailState =
  | { status: "loading"; matchId: string; match: null; error: null }
  | { status: "ready"; matchId: string; match: Match; error: null }
  | { status: "error"; matchId: string; match: null; error: unknown };

export function matchDetailLoadingState(matchId: string): MatchDetailState {
  return { status: "loading", matchId, match: null, error: null };
}

export async function getMatch(
  matchId: string,
  client: ApiClient = apiClient,
): Promise<MatchDetailState> {
  try {
    const match = await client.get<Match>(`/matches/${encodeURIComponent(matchId)}`);
    return { status: "ready", matchId, match, error: null };
  } catch (error) {
    return { status: "error", matchId, match: null, error };
  }
}

export type MatchRole = "requester" | "helper";

export type ReviewInput = {
  onTime: boolean;
  polite: boolean;
  safetyAware: boolean;
  communicative: boolean;
  comment: string;
};

export type Review = ReviewInput & {
  id: string;
  matchId: string;
  reviewerId: string;
  revieweeId: string;
  createdAt: string;
};

export function completeMatch(
  matchId: string,
  actorRole: MatchRole,
  client: ApiClient = apiClient,
): Promise<Match> {
  return client.post<Match>(`/matches/${encodeURIComponent(matchId)}/complete`, {
    completed: true,
    actorRole,
  });
}

export function disputeMatch(
  matchId: string,
  reason: string,
  client: ApiClient = apiClient,
): Promise<Match> {
  return client.post<Match>(`/matches/${encodeURIComponent(matchId)}/dispute`, {
    reason: reason.trim(),
  });
}

export function createReview(
  matchId: string,
  input: ReviewInput,
  client: ApiClient = apiClient,
): Promise<Review> {
  return client.post<Review>(`/matches/${encodeURIComponent(matchId)}/reviews`, {
    ...input,
    comment: input.comment.trim(),
  });
}

const matchErrorMessages: Record<string, string> = {
  AUTHENTICATION_REQUIRED: "セッションの有効期限が切れました。もう一度ログインしてください。",
  ROLE_FORBIDDEN: "この操作を行う権限がありません。",
  MATCH_NOT_FOUND: "マッチ情報が見つかりません。",
  MATCH_STATE_CONFLICT: "状態が更新されています。最新の情報を読み込んでください。",
  REVIEW_ALREADY_EXISTS: "このマッチにはレビュー済みです。",
};

export function matchActionErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return matchErrorMessages[error.code] ?? error.message;
  return "操作を完了できませんでした。通信環境を確認して、もう一度お試しください。";
}
