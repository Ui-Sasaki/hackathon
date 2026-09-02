import { apiClient, type ApiClient } from "./client";
import { ApiError } from "./errors";
import type { CreatedRequest } from "./request-creation";

export type RequestDetailState =
  | { status: "loading"; requestId: string; request: null; error: null }
  | { status: "ready"; requestId: string; request: CreatedRequest; error: null }
  | { status: "not_found"; requestId: string; request: null; error: ApiError }
  | { status: "error"; requestId: string; request: null; error: unknown };

export function requestDetailLoadingState(requestId: string): RequestDetailState {
  return { status: "loading", requestId, request: null, error: null };
}

export async function getRequestDetail(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<RequestDetailState> {
  try {
    const request = await client.get<CreatedRequest>(
      `/requests/${encodeURIComponent(requestId)}`,
    );
    return { status: "ready", requestId, request, error: null };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { status: "not_found", requestId, request: null, error };
    }
    return { status: "error", requestId, request: null, error };
  }
}
