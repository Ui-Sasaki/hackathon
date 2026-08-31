import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiNetworkError } from "./errors";
import { updateRequest, type UpdateRequestInput } from "./request-update";

function response(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const updated = {
  id: "request/with spaces",
  requesterId: "requester-from-session",
  title: "更新した依頼",
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
  version: 5,
  warnings: [],
  createdAt: "2026-08-31T01:00:00Z",
  updatedAt: "2026-08-31T03:00:00Z",
};

describe("TODO 14: request update API", () => {
  it("sends only editable fields with expectedVersion and retains the API version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, updated));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
    const input: UpdateRequestInput = { title: "更新した依頼", expectedVersion: 4 };

    await expect(updateRequest(updated.id, input, client)).resolves.toMatchObject({
      status: "updated",
      request: { id: updated.id, version: 5 },
    });
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.example.test/requests/request%2Fwith%20spaces");
    expect(options.method).toBe("PATCH");
    expect(JSON.parse(options.body as string)).toEqual(input);
    expect(options.body).not.toContain("requesterId");
    expect(options.body).not.toContain("updatedAt");
  });

  it.each([
    [403, "ROLE_FORBIDDEN", "forbidden"],
    [404, "REQUEST_NOT_FOUND", "not_found"],
    [422, "VALIDATION_ERROR", "validation_error"],
  ] as const)("maps %i %s to %s", async (status, code, expectedStatus) => {
    const fetchMock = vi.fn().mockResolvedValue(response(status, {
      error: { code, message: "更新できません", details: {}, requestId: "trace-update" },
    }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await updateRequest("request-1", { expectedVersion: 4 }, client);
    expect(state).toMatchObject({
      status: expectedStatus,
      requestId: "request-1",
      request: null,
      error: { status, code, requestId: "trace-update" },
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("refetches and retains the latest request after a 409 conflict", async () => {
    const latest = { ...updated, title: "別端末で更新済み", version: 6 };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(409, {
        error: {
          code: "REQUEST_STATE_CONFLICT",
          message: "依頼の状態が更新されています",
          details: { currentVersion: 6 },
          requestId: "trace-conflict",
        },
      }))
      .mockResolvedValueOnce(response(200, latest));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await updateRequest("request-1", { title: "競合する更新", expectedVersion: 4 }, client);
    expect(state).toMatchObject({
      status: "conflict",
      requestId: "request-1",
      latestRequest: { id: updated.id, title: "別端末で更新済み", version: 6 },
      error: { status: 409, code: "REQUEST_STATE_CONFLICT" },
      refreshError: null,
    });
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "https://api.example.test/requests/request-1",
      "https://api.example.test/requests/request-1",
    ]);
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe("GET");
  });

  it("preserves both the conflict and a failed latest-data refresh", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(409, {
        error: { code: "REQUEST_STATE_CONFLICT", message: "競合", details: {}, requestId: "trace" },
      }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await updateRequest("request-1", { expectedVersion: 4 }, client);
    expect(state).toMatchObject({ status: "conflict", latestRequest: null });
    expect(state.refreshError).toBeInstanceOf(ApiNetworkError);
  });

  it("keeps authentication and network failures retryable", async () => {
    const responses = [
      response(401, {
        error: { code: "AUTHENTICATION_REQUIRED", message: "ログインしてください", details: {}, requestId: "trace-auth" },
      }),
      new TypeError("Failed to fetch"),
    ];
    for (const result of responses) {
      const fetchMock = vi.fn();
      if (result instanceof Response) fetchMock.mockResolvedValue(result);
      else fetchMock.mockRejectedValue(result);
      const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
      const state = await updateRequest("request-1", { expectedVersion: 4 }, client);
      expect(state.status).toBe("error");
    }
  });
});
