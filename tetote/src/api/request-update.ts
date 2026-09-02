import { apiClient, type ApiClient } from "./client";
import { ApiError } from "./errors";
import { getRequestDetail } from "./request-detail";
import type { CreatedRequest } from "./request-creation";

export type UpdateRequestInput = {
  title?: string;
  description?: string;
  scheduledAt?: string;
  estimatedMinutes?: number;
  requiredHelpers?: number;
  expectedVersion: number;
};

export type RequestUpdateState =
  | { status: "updated"; requestId: string; request: CreatedRequest; latestRequest: null; error: null; refreshError: null }
  | { status: "conflict"; requestId: string; request: null; latestRequest: CreatedRequest | null; error: ApiError; refreshError: unknown }
  | { status: "forbidden" | "not_found" | "validation_error" | "error"; requestId: string; request: null; latestRequest: null; error: unknown; refreshError: null };

export async function updateRequest(
  requestId: string,
  input: UpdateRequestInput,
  client: ApiClient = apiClient,
): Promise<RequestUpdateState> {
  try {
    const request = await client.patch<CreatedRequest>(
      `/requests/${encodeURIComponent(requestId)}`,
      input,
    );
    return {
      status: "updated",
      requestId,
      request,
      latestRequest: null,
      error: null,
      refreshError: null,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      const latest = await getRequestDetail(requestId, client);
      return {
        status: "conflict",
        requestId,
        request: null,
        latestRequest: latest.status === "ready" ? latest.request : null,
        error,
        refreshError: latest.status === "ready" ? null : latest.error,
      };
    }
    const status = error instanceof ApiError
      ? ({ 403: "forbidden", 404: "not_found", 422: "validation_error" } as const)[error.status]
      : undefined;
    return {
      status: status ?? "error",
      requestId,
      request: null,
      latestRequest: null,
      error,
      refreshError: null,
    };
  }
}
