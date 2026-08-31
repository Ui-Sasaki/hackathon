import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../api/client";
import { ApiError, ApiNetworkError } from "../../api/errors";
import {
  applicationErrorMessage,
  applicantListLoadingState,
  createApplication,
  listApplicants,
  selectApplicant,
  selectionErrorMessage,
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

describe("TODO 18: applicant list API", () => {
  const applicant = {
    id: "application-1",
    requestId: "request/with spaces",
    helperId: "helper-from-session",
    message: "対応できます",
    availableAt: "2026-09-01T10:00:00+09:00",
    status: "applied" as const,
    createdAt: "2026-08-27T01:00:00Z",
    updatedAt: null,
    helper: {
      id: "helper-from-session",
      displayName: "応募者",
      verificationStatus: "approved" as const,
      universityVerified: true,
      skillTags: ["犬の散歩"],
      achievementCount: 3,
    },
  };

  it("provides a loading state before the request starts", () => {
    expect(applicantListLoadingState("request-1")).toEqual({
      status: "loading",
      requestId: "request-1",
      items: [],
      error: null,
    });
  });

  it("loads the server-filtered applicants without adding client filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, { items: [applicant] }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(listApplicants(applicant.requestId, client)).resolves.toEqual({
      status: "ready",
      requestId: applicant.requestId,
      items: [applicant],
      error: null,
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.test/requests/request%2Fwith%20spaces/applications",
    );
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("GET");
  });

  it("represents an empty API result explicitly", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(200, { items: [] })),
    });

    await expect(listApplicants("request-1", client)).resolves.toEqual({
      status: "empty",
      requestId: "request-1",
      items: [],
      error: null,
    });
  });

  it.each([
    [403, "ROLE_FORBIDDEN"],
    [404, "REQUEST_NOT_FOUND"],
  ])("keeps status %i and code %s in retryable error state", async (status, code) => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(status, {
        error: { code, message: "取得できません", details: {}, requestId: "trace-list" },
      }))
      .mockResolvedValueOnce(response(200, { items: [applicant] }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const failed = await listApplicants("request-1", client);
    expect(failed).toMatchObject({
      status: "error",
      requestId: "request-1",
      items: [],
      error: { status, code, requestId: "trace-list" },
    });
    await expect(listApplicants("request-1", client)).resolves.toMatchObject({
      status: "ready",
      items: [applicant],
    });
  });

  it("keeps a network failure in retryable error state", async () => {
    const networkError = new TypeError("Failed to fetch");
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockRejectedValue(networkError),
    });

    const failed = await listApplicants("request-1", client);
    expect(failed).toMatchObject({
      status: "error",
      requestId: "request-1",
      items: [],
      error: { cause: networkError },
    });
    expect(failed.error).toBeInstanceOf(ApiNetworkError);
  });
});

describe("TODO 19: applicant selection API", () => {
  const match = {
    id: "match-1",
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

  it("sends only expectedVersion and keeps the server match id and version", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(201, match));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(selectApplicant("application/with spaces", 4, client)).resolves.toEqual(match);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.test/applications/application%2Fwith%20spaces/select",
    );
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ expectedVersion: 4 });
    expect(init.body).not.toContain("requestId");
    expect(init.body).not.toContain("requesterId");
    expect(init.body).not.toContain("helperId");
  });

  it.each([
    [401, "AUTHENTICATION_REQUIRED"],
    [403, "ROLE_FORBIDDEN"],
    [404, "APPLICATION_NOT_FOUND"],
    [409, "REQUEST_STATE_CONFLICT"],
  ])("preserves status %i and selection code %s", async (status, code) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(status, {
        error: { code, message: "選択できません", details: {}, requestId: "trace-select" },
      })),
    });

    const error = await selectApplicant("application-1", 3, client).catch(
      (reason: unknown) => reason,
    );
    expect(error).toMatchObject({ status, code, requestId: "trace-select" });
    expect(selectionErrorMessage(error)).not.toBe("選択できません");
  });

  it("deduplicates selection while the same application is being submitted", async () => {
    let resolveResponse: ((value: Response) => void) | undefined;
    const fetchMock = vi.fn().mockImplementation(
      () => new Promise<Response>((resolve) => { resolveResponse = resolve; }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const first = selectApplicant("application-1", 3, client);
    const second = selectApplicant("application-1", 3, client);
    expect(second).toBe(first);
    expect(fetchMock).toHaveBeenCalledOnce();
    resolveResponse?.(response(201, match));
    await expect(first).resolves.toEqual(match);
  });
});
