import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiNetworkError } from "./errors";
import { deleteRequest } from "./request-deletion";
import type { CreatedRequest } from "./request-creation";

function response(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
  });
}

function request(id: string): CreatedRequest {
  return {
    id,
    requesterId: "requester-from-session",
    title: `依頼 ${id}`,
    description: "庭の落ち葉を一緒に片付けてください",
    category: "cleaning",
    riskLevel: "low",
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
}

const items = [request("request/with spaces"), request("request-2")];

describe("TODO 15: request deletion API", () => {
  it("removes only the deleted API ID from connected state after 204", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(204));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(deleteRequest(items[0].id, items, client)).resolves.toEqual({
      status: "deleted",
      requestId: items[0].id,
      items: [items[1]],
      error: null,
    });
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.example.test/requests/request%2Fwith%20spaces");
    expect(options.method).toBe("DELETE");
    expect(options.body).toBeUndefined();
  });

  it.each([
    [403, "ROLE_FORBIDDEN", "forbidden"],
    [404, "REQUEST_NOT_FOUND", "not_found"],
    [409, "INVALID_REQUEST_TRANSITION", "conflict"],
  ] as const)("maps %i %s to %s and preserves connected state", async (status, code, expected) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(status, {
        error: { code, message: "削除できません", details: {}, requestId: "trace-delete" },
      })),
    });

    const state = await deleteRequest("request-1", items, client);
    expect(state).toMatchObject({
      status: expected,
      requestId: "request-1",
      items,
      error: { status, code, requestId: "trace-delete" },
    });
  });

  it("treats a duplicate deletion as a 409 without removing more state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(204))
      .mockResolvedValueOnce(response(409, {
        error: {
          code: "INVALID_REQUEST_TRANSITION",
          message: "既に取り消されています",
          details: {},
          requestId: "trace-duplicate",
        },
      }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const first = await deleteRequest(items[0].id, items, client);
    const duplicate = await deleteRequest(items[0].id, first.items, client);
    expect(first).toMatchObject({ status: "deleted", items: [items[1]] });
    expect(duplicate).toMatchObject({
      status: "conflict",
      items: [items[1]],
      error: { status: 409, code: "INVALID_REQUEST_TRANSITION" },
    });
  });

  it("preserves connected state after authentication or network failure", async () => {
    const failures = [
      response(401, {
        error: { code: "AUTHENTICATION_REQUIRED", message: "ログインしてください", details: {}, requestId: "trace-auth" },
      }),
      new TypeError("Failed to fetch"),
    ];
    for (const failure of failures) {
      const fetchMock = vi.fn();
      if (failure instanceof Response) fetchMock.mockResolvedValue(failure);
      else fetchMock.mockRejectedValue(failure);
      const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
      const state = await deleteRequest(items[0].id, items, client);
      expect(state).toMatchObject({ status: "error", items });
      if (!(failure instanceof Response)) expect(state.error).toBeInstanceOf(ApiNetworkError);
    }
  });
});
