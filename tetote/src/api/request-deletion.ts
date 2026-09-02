import { apiClient, type ApiClient } from "./client";
import { ApiError } from "./errors";
import type { CreatedRequest } from "./request-creation";

export type RequestDeletionState =
  | { status: "deleted"; requestId: string; items: CreatedRequest[]; error: null }
  | { status: "forbidden" | "not_found" | "conflict" | "error"; requestId: string; items: CreatedRequest[]; error: unknown };

export async function deleteRequest(
  requestId: string,
  currentItems: CreatedRequest[],
  client: ApiClient = apiClient,
): Promise<RequestDeletionState> {
  try {
    await client.delete<void>(`/requests/${encodeURIComponent(requestId)}`);
    return {
      status: "deleted",
      requestId,
      items: currentItems.filter((item) => item.id !== requestId),
      error: null,
    };
  } catch (error) {
    const status = error instanceof ApiError
      ? ({ 403: "forbidden", 404: "not_found", 409: "conflict" } as const)[error.status]
      : undefined;
    return { status: status ?? "error", requestId, items: currentItems, error };
  }
}
