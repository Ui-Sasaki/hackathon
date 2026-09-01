import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient, warmUpApi } from "./client";
import { getApiBaseUrl } from "./config";
import { ApiAuthenticationError, ApiError, ApiNetworkError, ApiTimeoutError } from "./errors";

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
    const request = client.get("/requests", { retries: 0 });
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

describe("TODO 07: FastAPI error mapping", () => {
  it.each([401, 403, 404, 409, 422, 500])("preserves structured error fields for %i", async (status) => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(status, {
        error: {
          code: `ERROR_${status}`,
          message: `message ${status}`,
          details: { field: "title" },
          requestId: `trace_${status}`,
        },
      }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const error = await client.get("/requests").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    if (status === 401) expect(error).toBeInstanceOf(ApiAuthenticationError);
    expect(error).toMatchObject({
      status,
      code: `ERROR_${status}`,
      message: `message ${status}`,
      details: { field: "title" },
      requestId: `trace_${status}`,
    });
  });

  it.each([
    new Response("gateway unavailable", { status: 502, headers: { "Content-Type": "text/plain" } }),
    jsonResponse(500, { unexpected: true }),
  ])("safely maps malformed error responses", async (response) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response),
    });

    await expect(client.get("/requests")).rejects.toMatchObject({
      status: response.status,
      message: "通信処理に失敗しました",
      requestId: null,
    });
  });
});


describe("コールドスタートへの耐性", () => {
  function client(fetchMock: ReturnType<typeof vi.fn>) {
    return new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock as never });
  }

  function ok(body: unknown = { ok: true }) {
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  it("取得系は通信に失敗しても再試行する", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(ok({ status: "ok" }));

    const result = await client(fetchMock).get("/health", { retryDelayMs: 0 });

    expect(result).toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("再試行の回数には上限がある", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(
      client(fetchMock).get("/health", { retries: 2, retryDelayMs: 0 }),
    ).rejects.toBeInstanceOf(ApiNetworkError);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("作成系は再送しない", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(
      client(fetchMock).post("/requests", { title: "テスト" }, { retryDelayMs: 0 }),
    ).rejects.toBeInstanceOf(ApiNetworkError);
    // 二重登録を避けるため、1回で諦める。
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("応答が返ってきた失敗は再試行しない", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "AUTHENTICATION_REQUIRED", message: "x" } }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      client(fetchMock).get("/profile", { retryDelayMs: 0 }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("サーバーを起こせたかを返す", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(ok({ status: "ok" }));

    await expect(
      warmUpApi(client(fetchMock), { retryDelayMs: 0 }),
    ).resolves.toBe(true);
  });

  it("起こせなくても例外にしない", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(
      warmUpApi(client(fetchMock), { retryDelayMs: 0 }),
    ).resolves.toBe(false);
  });
});
