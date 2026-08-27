import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { getApiBaseUrl } from "./config";
import { ApiAuthenticationError, ApiNetworkError, ApiTimeoutError } from "./errors";

const jsonResponse = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("TODO 05: API client foundation", () => {
  it("reads and normalizes EXPO_PUBLIC_API_URL", () => {
    vi.stubEnv("EXPO_PUBLIC_API_URL", "https://api.example.test/base/");
    expect(getApiBaseUrl()).toBe("https://api.example.test/base");
  });

  it("uses the configured base URL, cookies, and common JSON headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { id: "request-1" }));
    const client = new ApiClient({ baseUrl: "https://api.example.test/", fetch: fetchMock });

    await expect(client.get<{ id: string }>("/requests")).resolves.toEqual({ id: "request-1" });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.test/requests",
      expect.objectContaining({ credentials: "include", method: "GET" }),
    );
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.has("Content-Type")).toBe(false);
  });

  it("serializes JSON without adding identity, role, actor, or time fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, { id: "request-1" }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await client.post("/requests", { title: "雪かきのお手伝い" });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({ title: "雪かきのお手伝い" });
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("classifies network failures", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    });
    await expect(client.get("/requests")).rejects.toBeInstanceOf(ApiNetworkError);
  });

  it("classifies timeouts", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_url: string | URL | Request, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock, timeoutMs: 25 });
    const request = client.get("/requests");
    const expectation = expect(request).rejects.toBeInstanceOf(ApiTimeoutError);
    await vi.advanceTimersByTimeAsync(25);
    await expectation;
  });
});

describe("TODO 06: authenticated mutations", () => {
  it.each([
    ["GET", undefined],
    ["PATCH", { title: "更新" }],
  ])("uses the current SDK-intercepted fetch for %s requests", async (method, body) => {
    const originalFetch = vi.fn();
    vi.stubGlobal("fetch", originalFetch);
    const client = new ApiClient({ baseUrl: "https://api.example.test" });
    const sdkInterceptedFetch = vi.fn().mockResolvedValue(jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", sdkInterceptedFetch);

    await client.request("/requests/request-1", { method, body });

    expect(originalFetch).not.toHaveBeenCalled();
    expect(sdkInterceptedFetch).toHaveBeenCalledOnce();
    expect(sdkInterceptedFetch.mock.calls[0][1]).toEqual(
      expect.objectContaining({ credentials: "include", method }),
    );
  });

  it("maps an expired session response to an authentication error", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(jsonResponse(401)),
    });

    await expect(client.patch("/profile", {})).rejects.toBeInstanceOf(ApiAuthenticationError);
  });
});
