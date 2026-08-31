import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../api/client";
import { ApiError } from "../../api/errors";
import {
  applicationErrorMessage,
  createApplication,
  withdrawalErrorMessage,
  withdrawApplication,
} from "./client";

const response = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("TODO 16: application creation API", () => {
  it("sends only the reason and available date to the selected request", async () => {
    const application = {
      id: "application-1",
      requestId: "request/with spaces",
      helperId: "helper-from-session",
      message: "犬の散歩経験があります",
      availableAt: "2026-09-01T10:00:00+09:00",
      status: "applied" as const,
      createdAt: "2026-08-27T01:00:00Z",
      updatedAt: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(response(201, application));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(
      createApplication(
        "request/with spaces",
        {
          message: "犬の散歩経験があります",
          availableAt: "2026-09-01T10:00:00+09:00",
        },
        client,
      ),
    ).resolves.toEqual(application);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.test/requests/request%2Fwith%20spaces/applications",
    );
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      message: "犬の散歩経験があります",
      availableAt: "2026-09-01T10:00:00+09:00",
    });
    expect(init.body).not.toContain("helperId");
    expect(init.body).not.toContain("createdAt");
    expect(init.body).not.toContain("status");
  });

  it.each([
    [403, "SELF_APPLICATION_NOT_ALLOWED", "自分の依頼には応募できません。"],
    [403, "VERIFICATION_REQUIRED", "この依頼への応募には本人確認が必要です。"],
    [409, "DUPLICATE_APPLICATION", "この依頼には応募済みです。"],
    [409, "REQUEST_EXPIRED", "この依頼の募集期限は終了しました。"],
    [409, "REQUEST_NOT_OPEN", "この依頼は現在募集していません。"],
  ])("reflects status %i and code %s in the application state", async (status, code, message) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(
        response(status, {
          error: {
            code,
            message: "応募できません",
            details: {},
            requestId: "trace-application",
          },
        }),
      ),
    });

    const result = createApplication(
      "request-1",
      {
        message: "お手伝いできます",
        availableAt: "2026-09-01T10:00:00+09:00",
      },
      client,
    );

    const error = await result.catch((reason: unknown) => reason);
    expect(error).toMatchObject({
      status,
      code,
      requestId: "trace-application",
    } satisfies Partial<ApiError>);
    expect(applicationErrorMessage(error)).toBe(message);
  });

  it("uses the API message for an unrecognized application error", () => {
    const error = new ApiError({
      status: 409,
      code: "APPLICATION_CONFLICT",
      message: "依頼の状態が更新されています",
    });

    expect(applicationErrorMessage(error)).toBe("依頼の状態が更新されています");
  });

  it("uses a retryable message for network failures", () => {
    expect(applicationErrorMessage(new TypeError("Failed to fetch"))).toBe(
      "応募を送信できませんでした。通信環境を確認して、もう一度お試しください。",
    );
  });
});

describe("TODO 17: application withdrawal API", () => {
  const application = {
    id: "application/with spaces",
    requestId: "request-1",
    helperId: "helper-from-session",
    message: "対応できます",
    availableAt: "2026-09-01T10:00:00+09:00",
    status: "withdrawn" as const,
    createdAt: "2026-08-27T01:00:00Z",
    updatedAt: "2026-08-31T02:00:00Z",
  };

  it("posts no client-owned fields and returns the server application state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, application));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(withdrawApplication(application.id, client)).resolves.toEqual(application);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.test/applications/application%2Fwith%20spaces/withdraw",
    );
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it.each([
    [401, "AUTHENTICATION_REQUIRED", "セッションの有効期限が切れました。もう一度ログインしてください。"],
    [403, "ROLE_FORBIDDEN", "この応募を取り下げる権限がありません。"],
    [404, "APPLICATION_NOT_FOUND", "応募が見つかりません。"],
    [409, "APPLICATION_NOT_WITHDRAWABLE", "この応募はすでに取り下げ済みか、現在の状態では取り下げできません。"],
  ])("preserves status %i and safely maps code %s", async (status, code, message) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(status, {
        error: { code, message: "API error", details: {}, requestId: "trace-withdrawal" },
      })),
    });

    const error = await withdrawApplication("application-1", client).catch(
      (reason: unknown) => reason,
    );

    expect(error).toMatchObject({ status, code, requestId: "trace-withdrawal" });
    expect(withdrawalErrorMessage(error)).toBe(message);
  });

  it("uses a retryable message for network failures", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    });

    const error = await withdrawApplication("application-1", client).catch(
      (reason: unknown) => reason,
    );
    expect(withdrawalErrorMessage(error)).toBe(
      "応募を取り下げできませんでした。通信環境を確認して、もう一度お試しください。",
    );
  });

  it("deduplicates withdrawal while the same application is being submitted", async () => {
    let resolveResponse: ((value: Response) => void) | undefined;
    const fetchMock = vi.fn().mockImplementation(
      () => new Promise<Response>((resolve) => { resolveResponse = resolve; }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const first = withdrawApplication("application-1", client);
    const second = withdrawApplication("application-1", client);

    expect(second).toBe(first);
    expect(fetchMock).toHaveBeenCalledOnce();
    resolveResponse?.(response(200, application));
    await expect(first).resolves.toEqual(application);
  });
});
