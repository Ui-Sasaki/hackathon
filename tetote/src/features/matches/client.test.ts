import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../api/client";
import { ApiError, ApiNetworkError } from "../../api/errors";
import { completeMatch, createReview, disputeMatch, getMatch, matchDetailLoadingState } from "./client";

const response = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("TODO 20: match detail API", () => {
  const match = {
    id: "match/with spaces",
    requestId: "request-1",
    requesterId: "requester-from-session",
    helperId: "helper-1",
    status: "matched" as const,
    requesterConfirmed: false,
    helperConfirmed: false,
    matchedAt: "2026-08-31T03:00:00Z",
    completedAt: null,
    disputeReason: null,
    disputedAt: null,
    version: 1,
  };

  it("provides loading state before fetching", () => {
    expect(matchDetailLoadingState("match-1")).toEqual({
      status: "loading",
      matchId: "match-1",
      match: null,
      error: null,
    });
  });

  it("loads and preserves the match status, id, and version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, match));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(getMatch(match.id, client)).resolves.toEqual({
      status: "ready",
      matchId: match.id,
      match,
      error: null,
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.test/matches/match%2Fwith%20spaces",
    );
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("GET");
  });

  it.each([
    [401, "AUTHENTICATION_REQUIRED"],
    [403, "ROLE_FORBIDDEN"],
    [404, "MATCH_NOT_FOUND"],
  ])("keeps status %i and code %s in retryable error state", async (status, code) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(status, {
        error: { code, message: "取得できません", details: {}, requestId: "trace-match" },
      })),
    });

    const result = await getMatch("match-1", client);
    expect(result).toMatchObject({
      status: "error",
      matchId: "match-1",
      match: null,
      error: { status, code, requestId: "trace-match" },
    });
    if (result.status === "error") expect(result.error).toBeInstanceOf(ApiError);
  });

  it("keeps a network failure in retryable error state", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    });

    const result = await getMatch("match-1", client);
    expect(result).toMatchObject({ status: "error", matchId: "match-1", match: null });
    if (result.status === "error") expect(result.error).toBeInstanceOf(ApiNetworkError);
  });
});

describe("match actions", () => {
  it("connects completion, dispute, and review without sending actor identity", async () => {
    const match = { id: "match/1", status: "matched" };
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify(match), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock as never });

    await completeMatch("match/1", "helper", client);
    await disputeMatch("match/1", "予定と異なる作業を求められました", client);
    await createReview("match/1", {
      onTime: true,
      polite: true,
      safetyAware: true,
      communicative: true,
      comment: " ありがとうございました ",
    }, client);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://api.test/matches/match%2F1/complete",
      "http://api.test/matches/match%2F1/dispute",
      "http://api.test/matches/match%2F1/reviews",
    ]);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ completed: true, actorRole: "helper" });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ reason: "予定と異なる作業を求められました" });
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
      onTime: true, polite: true, safetyAware: true, communicative: true, comment: "ありがとうございました",
    });
  });
});
