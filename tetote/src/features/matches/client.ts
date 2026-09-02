import { apiClient, type ApiClient } from "../../api/client";

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
