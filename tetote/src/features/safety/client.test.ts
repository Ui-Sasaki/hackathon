import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../api/client";
import { ApiAuthenticationError, ApiError, ApiNetworkError } from "../../api/errors";
import {
  fetchRequestOwner,
  safetyErrorMessage,
  setUserBlocked,
  submitReport,
  validateReport,
} from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, code: string): Response {
  return jsonResponse(
    { error: { code, message: "サーバーの文言", details: {}, requestId: "trace_1" } },
    status,
  );
}

function clientWith(fetchMock: ReturnType<typeof vi.fn>): ApiClient {
  return new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock as never });
}

const REPORT = {
  id: "rep_1",
  reporterId: "usr_101",
  targetType: "request",
  targetId: "req_1",
  reason: "dangerous_work",
  description: "高所での作業を頼まれました",
  severity: "high",
  status: "open",
  createdAt: "2026-09-03T00:00:00Z",
};

describe("通報の送信", () => {
  it("対象・理由・説明だけを送り、通報者や重大度は送らない", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(REPORT, 201));

    await submitReport(
      {
        targetType: "request",
        targetId: "req_1",
        reason: "dangerous_work",
        description: "  高所での作業を頼まれました  ",
      },
      clientWith(fetchMock),
    );

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/reports");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(JSON.parse(init.body)).toEqual({
      targetType: "request",
      targetId: "req_1",
      reason: "dangerous_work",
      description: "高所での作業を頼まれました",
    });
  });

  it("サーバーが決めた重大度を返す", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(REPORT, 201));

    const report = await submitReport(
      {
        targetType: "request",
        targetId: "req_1",
        reason: "dangerous_work",
        description: "高所での作業を頼まれました",
      },
      clientWith(fetchMock),
    );

    expect(report.severity).toBe("high");
  });
});

describe("入力検証", () => {
  it("理由が未選択なら止める", () => {
    expect(validateReport({ reason: null, description: "十分に長い説明です。" })).toContain(
      "理由",
    );
  });

  it("説明が10文字未満なら止める", () => {
    expect(validateReport({ reason: "other", description: "短い" })).toContain("10文字");
  });

  it("条件を満たせば通す", () => {
    expect(
      validateReport({ reason: "other", description: "約束の時間に来ませんでした。" }),
    ).toBeNull();
  });
});

describe("ブロックと解除", () => {
  it("ブロックはblocked=trueで送る", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ userId: "usr_301", blocked: true, updatedAt: "2026-09-03T00:00:00Z" }, 201),
      );

    const result = await setUserBlocked("usr_301", true, clientWith(fetchMock));

    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/users/usr_301/block");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ blocked: true });
    expect(result.blocked).toBe(true);
  });

  it("解除はblocked=falseで送る", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ userId: "usr_301", blocked: false, updatedAt: "2026-09-03T00:00:00Z" }, 201),
      );

    const result = await setUserBlocked("usr_301", false, clientWith(fetchMock));

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ blocked: false });
    expect(result.blocked).toBe(false);
  });

  it("操作者のIDは送らない", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ userId: "usr_301", blocked: true, updatedAt: "2026-09-03T00:00:00Z" }, 201),
      );

    await setUserBlocked("usr_301", true, clientWith(fetchMock));

    expect(Object.keys(JSON.parse(fetchMock.mock.calls[0][1].body))).toEqual(["blocked"]);
  });

  it("自己ブロックのエラーを文言へ変える", async () => {
    const fetchMock = vi.fn().mockResolvedValue(errorResponse(422, "SELF_BLOCK_NOT_ALLOWED"));

    await expect(setUserBlocked("usr_101", true, clientWith(fetchMock))).rejects.toSatisfy(
      (error: unknown) => safetyErrorMessage(error) === "自分自身はブロックできません",
    );
  });
});

describe("依頼の所有者の取得", () => {
  it("依頼者IDだけを返す", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ id: "req_1", requesterId: "usr_301", title: "x" }));

    await expect(fetchRequestOwner("req_1", clientWith(fetchMock))).resolves.toBe("usr_301");
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/requests/req_1");
  });
});

describe("失敗の表示", () => {
  it.each([
    [new ApiAuthenticationError(), "ログイン"],
    [new ApiError({ status: 403, code: "ROLE_FORBIDDEN", message: "x" }), "権限"],
    [new ApiError({ status: 404, code: "USER_PROFILE_NOT_FOUND", message: "x" }), "見つかりません"],
    [new ApiError({ status: 409, code: "STATE_CONFLICT", message: "x" }), "開き直して"],
    [new ApiError({ status: 422, code: "VALIDATION_ERROR", message: "x" }), "入力内容"],
    [new ApiNetworkError(), "通信できません"],
  ])("%s を利用者向けの文言にする", (error, fragment) => {
    expect(safetyErrorMessage(error)).toContain(fragment);
  });

  it("サーバーの文言をそのまま出さない", () => {
    const error = new ApiError({ status: 500, code: "X", message: "stack trace" });
    expect(safetyErrorMessage(error)).not.toContain("stack trace");
  });
});
