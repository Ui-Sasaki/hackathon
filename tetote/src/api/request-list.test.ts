import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiNetworkError } from "./errors";
import { listRequests, requestListLoadingState } from "./request-list";

function response(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const item = {
  id: "request-1",
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

const origin = { areaCode: "AREA-001", source: "selected_region" as const };

describe("TODO 12: request list API", () => {
  it("starts with an explicit loading state for the selected filters", () => {
    const filters = { category: "pet support", areaCode: "AREA/001" };
    expect(requestListLoadingState(filters)).toEqual({
      status: "loading",
      filters,
      items: [],
      nextCursor: null,
      origin: null,
      error: null,
    });
  });

  it("passes category and approximate area filters and keeps API IDs and versions", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, {
      items: [item], nextCursor: null, origin,
    }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
    const filters = { category: "pet support", areaCode: "AREA/001" };

    await expect(listRequests(filters, client)).resolves.toEqual({
      status: "ready",
      filters,
      items: [item],
      nextCursor: null,
      origin,
      error: null,
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.test/requests?category=pet+support&areaCode=AREA%2F001",
    );
    expect(fetchMock.mock.calls[0][0]).not.toContain("latitude");
    expect(fetchMock.mock.calls[0][0]).not.toContain("longitude");
  });

  it("represents an empty API result without fixed fallback requests", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(200, {
        items: [], nextCursor: null, origin,
      })),
    });

    await expect(listRequests({}, client)).resolves.toEqual({
      status: "empty",
      filters: {},
      items: [],
      nextCursor: null,
      origin,
      error: null,
    });
  });

  it.each([
    [401, "AUTHENTICATION_REQUIRED"],
    [422, "VALIDATION_ERROR"],
  ])("keeps %i %s as an error that can be retried with the same filters", async (status, code) => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(status, {
        error: { code, message: "取得できません", details: {}, requestId: "trace-list" },
      }))
      .mockResolvedValueOnce(response(200, { items: [item], nextCursor: null, origin }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
    const filters = { category: "cleaning", areaCode: "AREA-001" };

    const failed = await listRequests(filters, client);
    expect(failed).toMatchObject({
      status: "error",
      filters,
      items: [],
      error: { status, code, requestId: "trace-list" },
    });
    await expect(listRequests(failed.filters, client)).resolves.toMatchObject({
      status: "ready",
      filters,
      items: [{ id: "request-1", version: 4 }],
    });
  });

  it("keeps a network failure in retryable error state without mock data", async () => {
    const networkError = new TypeError("Failed to fetch");
    const filters = { areaCode: "AREA-001" };
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockRejectedValue(networkError),
    });

    const failed = await listRequests(filters, client);
    expect(failed).toMatchObject({ status: "error", filters, items: [] });
    expect(failed.error).toBeInstanceOf(ApiNetworkError);
  });
});
