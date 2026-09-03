import { apiClient, type ApiClient } from "./client";
import { ApiError } from "./errors";
import type { CreatedRequest } from "./request-creation";

/**
 * 下書き（draft）の依頼を公開して、支援者の一覧に載せる。
 * 作成API（POST /requests）は下書きを作るだけなので、依頼者が「この内容で依頼する」
 * と決めたときにこの呼び出しで公開へ進める。
 */
export type RequestPublishState =
  | { status: "published"; requestId: string; request: CreatedRequest; error: null }
  | {
      status: "forbidden" | "not_found" | "under_review" | "conflict" | "error";
      requestId: string;
      request: null;
      error: unknown;
    };

export async function publishRequest(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<RequestPublishState> {
  try {
    const request = await client.post<CreatedRequest>(
      `/requests/${encodeURIComponent(requestId)}/publish`,
    );
    return { status: "published", requestId, request, error: null };
  } catch (error) {
    if (error instanceof ApiError && error.status === 409 && error.code === "REQUEST_UNDER_REVIEW") {
      return { status: "under_review", requestId, request: null, error };
    }
    const status = error instanceof ApiError
      ? ({ 403: "forbidden", 404: "not_found", 409: "conflict" } as const)[error.status]
      : undefined;
    return { status: status ?? "error", requestId, request: null, error };
  }
}
