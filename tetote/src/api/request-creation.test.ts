import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiNetworkError } from "./errors";
import {
  beginRequestCreation,
  submitRequestCreation,
  type CreateRequestInput,
} from "./request-creation";

function response(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const input: CreateRequestInput = {
  title: "庭の片付け",
  description: "庭の落ち葉を一緒に片付けてください",
  category: "cleaning",
  scheduledAt: "2026-09-02T10:00:00+09:00",
  estimatedMinutes: 30,
  requiredHelpers: 1,
  areaCode: "AREA-001",
  riskLevel: "low",
  confirmed: true,
};

const created = {
  id: "request-1",
  requesterId: "user-from-session",
  ...input,
  riskLevel: "low" as const,
  areaLabel: "大学周辺・約1km",
  distanceKm: 1,
  acceptedHelpers: 0,
  status: "draft",
  version: 1,
  warnings: [],
  createdAt: "2026-08-31T01:00:00Z",
  updatedAt: "2026-08-31T01:00:00Z",
};

describe("TODO 11: request creation API", () => {
  it("posts only the allowed confirmed request fields and retains server identity and version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(201, created));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
    const attempt = beginRequestCreation(input, () => "operation-1");

    await expect(submitRequestCreation(attempt, client)).resolves.toEqual({
      status: "created",
      attempt,
      request: created,
      error: null,
    });

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://api.example.test/requests");
    expect(options.method).toBe("POST");
    expect(new Headers(options.headers).get("Idempotency-Key")).toBe("operation-1");
    expect(JSON.parse(options.body as string)).toEqual(input);
    expect(options.body).not.toContain("requesterId");
    expect(options.body).not.toContain("createdAt");
    expect(options.body).not.toContain("updatedAt");
    expect(options.body).not.toContain("status");
  });

  it("reuses the same idempotency key when a network failure is retried", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(response(201, created));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
    const attempt = beginRequestCreation(input, () => "stable-operation");

    const failed = await submitRequestCreation(attempt, client);
    expect(failed.status).toBe("error");
    expect(failed.error).toBeInstanceOf(ApiNetworkError);
    await expect(submitRequestCreation(failed.attempt, client)).resolves.toMatchObject({
      status: "created",
      request: { id: "request-1", version: 1 },
    });
    expect(fetchMock.mock.calls.map((call) => {
      const options = call[1] as RequestInit;
      return new Headers(options.headers).get("Idempotency-Key");
    })).toEqual(["stable-operation", "stable-operation"]);
  });

  it.each([
    [409, "REQUEST_STATE_CONFLICT", "conflict"],
    [422, "VALIDATION_ERROR", "validation_error"],
  ] as const)("maps %i %s to %s while preserving the retry attempt", async (status, code, expected) => {
    const fetchMock = vi.fn().mockResolvedValue(response(status, {
      error: { code, message: "作成できません", details: {}, requestId: "trace-create" },
    }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
    const attempt = beginRequestCreation(input, () => "operation-error");

    const state = await submitRequestCreation(attempt, client);
    expect(state).toMatchObject({
      status: expected,
      attempt,
      request: null,
      error: { status, code, requestId: "trace-create" },
    });
  });
});
