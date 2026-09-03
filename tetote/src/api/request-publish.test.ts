import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { publishRequest } from "./request-publish";

function response(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, code: string): Response {
  return response(status, { error: { code, message: code, details: {}, requestId: "req-1" } });
}

const published = {
  id: "request/1",
  requesterId: "user-from-session",
  title: "庭の片付け",
  description: "庭の落ち葉を一緒に片付けてください",
  category: "cleaning",
  riskLevel: "low" as const,
  areaCode: "AREA-001",
  areaLabel: "大学周辺・約1km",
  distanceKm: 1,
  acceptedHelpers: 0,
  scheduledAt: "2026-09-10T10:00:00+09:00",
  estimatedMinutes: 30,
  requiredHelpers: 1,
  status: "published",
  version: 2,
  warnings: [],
  createdAt: "2026-09-03T01:00:00Z",
  updatedAt: "2026-09-03T01:00:00Z",
};

describe("依頼の公開API", () => {
  it("公開エンドポイントをPOSTで呼び、公開後の依頼を返す", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, published));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(publishRequest(published.id, client)).resolves.toEqual({
      status: "published",
      requestId: published.id,
      request: published,
      error: null,
    });

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.example.test/requests/request%2F1/publish");
    expect(options.method).toBe("POST");
    expect(options.body).toBeUndefined();
  });

  it("審査待ちは under_review として区別する", async () => {
    const fetchMock = vi.fn().mockResolvedValue(errorResponse(409, "REQUEST_UNDER_REVIEW"));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await publishRequest("request-1", client);

    expect(state.status).toBe("under_review");
    expect(state.request).toBeNull();
  });

  it.each([
    [403, "ROLE_FORBIDDEN", "forbidden"],
    [404, "REQUEST_NOT_FOUND", "not_found"],
    [409, "INVALID_REQUEST_TRANSITION", "conflict"],
    [500, "INTERNAL_ERROR", "error"],
  ])("HTTP %s は %s として返す", async (status, code, expected) => {
    const fetchMock = vi.fn().mockResolvedValue(errorResponse(status, code));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await publishRequest("request-1", client);

    expect(state.status).toBe(expected);
    expect(state.request).toBeNull();
    expect(state.error).toBeTruthy();
  });
});
