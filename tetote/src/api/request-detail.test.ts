import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiNetworkError } from "./errors";
import { getRequestDetail, requestDetailLoadingState } from "./request-detail";

function response(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const request = {
  id: "request/with spaces",
  requesterId: "requester-1",
  title: "庭の片付け",
  description: "庭の落ち葉を一緒に片付けてください",
  category: "cleaning",
  riskLevel: "low" as const,
  areaCode: "AREA-001",
  areaLabel: "大学周辺・約1km",
  distanceKm: 1,
  acceptedHelpers: 0,
  scheduledAt: "2026-09-02T10:00:00+09:00",
  estimatedMinutes: 30,
  requiredHelpers: 1,
  status: "published",
  version: 4,
  warnings: [],
  createdAt: "2026-08-31T01:00:00Z",
  updatedAt: "2026-08-31T02:00:00Z",
};

describe("TODO 13: request detail API", () => {
  it("starts with a loading state for the requested API ID", () => {
    expect(requestDetailLoadingState(request.id)).toEqual({
      status: "loading",
      requestId: request.id,
      request: null,
      error: null,
    });
  });

  it("encodes the path and retains the API response ID and version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, request));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(getRequestDetail(request.id, client)).resolves.toEqual({
      status: "ready",
      requestId: request.id,
      request,
      error: null,
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.test/requests/request%2Fwith%20spaces",
    );
  });

  it("distinguishes a hidden or missing request as not found", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(404, {
        error: {
          code: "REQUEST_NOT_FOUND",
          message: "依頼が見つかりません",
          details: {},
          requestId: "trace-detail",
        },
      })),
    });

    const state = await getRequestDetail("missing", client);
    expect(state).toMatchObject({
      status: "not_found",
      requestId: "missing",
      request: null,
      error: { status: 404, code: "REQUEST_NOT_FOUND", requestId: "trace-detail" },
    });
  });

  it("keeps authentication failure as a retryable error", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(401, {
        error: {
          code: "AUTHENTICATION_REQUIRED",
          message: "ログインしてください",
          details: {},
          requestId: "trace-auth",
        },
      })),
    });

    const state = await getRequestDetail("request-1", client);
    expect(state).toMatchObject({
      status: "error",
      requestId: "request-1",
      error: { status: 401, code: "AUTHENTICATION_REQUIRED" },
    });
  });

  it("distinguishes a network failure and preserves the ID for retry", async () => {
    const networkError = new TypeError("Failed to fetch");
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockRejectedValue(networkError),
    });

    const state = await getRequestDetail("request-1", client);
    expect(state).toMatchObject({ status: "error", requestId: "request-1", request: null });
    expect(state.error).toBeInstanceOf(ApiNetworkError);
  });
});
