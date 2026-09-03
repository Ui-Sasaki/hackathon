import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../api/client";
import type { StructuredRequestDraft } from "../../api/request-structuring";
import {
  buildCreateRequestInput,
  estimatedMinutesFromLabel,
  scheduledAtFromDeadline,
  submissionErrorMessage,
  submitAndPublishRequest,
} from "./submit";

const draft: StructuredRequestDraft = {
  title: "庭の片付け",
  description: "庭の落ち葉を一緒に片付けてください",
  category: "cleaning",
  scheduledAt: "2026-09-10T10:00:00+09:00",
  estimatedMinutes: 45,
  approximateArea: "AREA-002",
  requiredHelpers: 2,
  itemsToBring: [],
  riskLevel: "low",
  riskCandidates: [],
  missingFields: [],
  warnings: [],
};

const NOW = new Date("2026-09-03T09:00:00Z");

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, code: string): Response {
  return jsonResponse({ error: { code, message: code, details: {}, requestId: "req-1" } }, status);
}

const created = {
  id: "request-1",
  requesterId: "user-from-session",
  title: draft.title,
  description: draft.description,
  category: draft.category,
  riskLevel: "low" as const,
  areaCode: "AREA-002",
  areaLabel: "大学北側・約1km",
  distanceKm: 1,
  acceptedHelpers: 0,
  scheduledAt: draft.scheduledAt as string,
  estimatedMinutes: 45,
  requiredHelpers: 2,
  status: "draft",
  version: 1,
  warnings: [],
  createdAt: "2026-09-03T09:00:00Z",
  updatedAt: "2026-09-03T09:00:00Z",
};

describe("作成APIへ送る形の組み立て", () => {
  it("AIの下書きが揃っていればそのまま使う", () => {
    const result = buildCreateRequestInput(draft, {}, { now: NOW });

    expect(result.problem).toBeNull();
    expect(result.input).toEqual({
      title: "庭の片付け",
      description: "庭の落ち葉を一緒に片付けてください",
      category: "cleaning",
      scheduledAt: "2026-09-10T10:00:00+09:00",
      estimatedMinutes: 45,
      requiredHelpers: 2,
      areaCode: "AREA-002",
      riskLevel: "low",
      confirmed: true,
    });
  });

  it("足りない項目は手入力のラベルと既定値で補う", () => {
    const sparse: StructuredRequestDraft = {
      ...draft,
      title: "  ",
      category: "",
      scheduledAt: null,
      estimatedMinutes: null,
      requiredHelpers: null,
      approximateArea: null,
    };

    const result = buildCreateRequestInput(
      sparse,
      { time: "1時間〜2時間", deadline: "24時間後" },
      { now: NOW, fallbackAreaCode: "AREA-003" },
    );

    expect(result.problem).toBeNull();
    expect(result.input).toMatchObject({
      title: "庭の落ち葉を一緒に片付けてください",
      category: "other",
      estimatedMinutes: 120,
      requiredHelpers: 1,
      areaCode: "AREA-003",
      scheduledAt: "2026-09-04T09:00:00.000Z",
    });
  });

  it("ラベルも無ければ30分・3日後・大学周辺になる", () => {
    const sparse: StructuredRequestDraft = {
      ...draft,
      scheduledAt: null,
      estimatedMinutes: null,
      approximateArea: null,
    };

    const result = buildCreateRequestInput(sparse, {}, { now: NOW });

    expect(result.input).toMatchObject({
      estimatedMinutes: 30,
      areaCode: "AREA-001",
      scheduledAt: "2026-09-06T09:00:00.000Z",
    });
  });

  it("AIが過去の日時や読めない日時を返したら、期限のラベルから決め直す", () => {
    const past = buildCreateRequestInput(
      { ...draft, scheduledAt: "2026-08-19T17:00:00+09:00" },
      { deadline: "1週間後" },
      { now: NOW },
    );
    const broken = buildCreateRequestInput(
      { ...draft, scheduledAt: "not-a-date" },
      {},
      { now: NOW },
    );

    expect(past.input?.scheduledAt).toBe("2026-09-10T09:00:00.000Z");
    expect(broken.input?.scheduledAt).toBe("2026-09-06T09:00:00.000Z");
  });

  it("所要時間はサーバーが受け付ける範囲へ丸める", () => {
    const tooLong = buildCreateRequestInput({ ...draft, estimatedMinutes: 600 }, {}, { now: NOW });
    const tooShort = buildCreateRequestInput({ ...draft, estimatedMinutes: 3 }, {}, { now: NOW });

    expect(tooLong.input?.estimatedMinutes).toBe(240);
    expect(tooShort.input?.estimatedMinutes).toBe(10);
  });

  it("依頼内容が空なら送らずに問題を返す", () => {
    const result = buildCreateRequestInput({ ...draft, description: "   " });

    expect(result.input).toBeNull();
    expect(result.problem).toContain("依頼内容");
  });

  it("危険度は low / medium 以外を low に寄せる", () => {
    const result = buildCreateRequestInput({ ...draft, riskLevel: "high" });

    expect(result.input?.riskLevel).toBe("low");
  });

  it("ラベルの対応表", () => {
    expect(estimatedMinutesFromLabel("15分以内")).toBe(15);
    expect(estimatedMinutesFromLabel("半日")).toBe(240);
    expect(estimatedMinutesFromLabel("知らない値")).toBeNull();
    expect(estimatedMinutesFromLabel(undefined)).toBeNull();
    expect(scheduledAtFromDeadline("1週間後", NOW)).toBe("2026-09-10T09:00:00.000Z");
    expect(scheduledAtFromDeadline(undefined, NOW)).toBe("2026-09-06T09:00:00.000Z");
  });
});

describe("依頼の作成と公開", () => {
  const input = buildCreateRequestInput(draft, {}, { now: NOW }).input!;

  it("作成してから公開し、公開後の依頼を返す", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(created, 201))
      .mockResolvedValueOnce(jsonResponse({ ...created, status: "published", version: 2 }));
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock });

    const state = await submitAndPublishRequest(input, client, () => "key-1");

    expect(state).toEqual({
      status: "published",
      request: { ...created, status: "published", version: 2 },
      error: null,
    });
    const [createUrl, createOptions] = fetchMock.mock.calls[0] as [string, RequestInit];
    const [publishUrl, publishOptions] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(createUrl).toBe("http://api.test/requests");
    expect(createOptions.method).toBe("POST");
    expect(new Headers(createOptions.headers).get("Idempotency-Key")).toBe("key-1");
    expect(publishUrl).toBe("http://api.test/requests/request-1/publish");
    expect(publishOptions.method).toBe("POST");
  });

  it("審査対象として作られた依頼は公開を呼ばない", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(jsonResponse({ ...created, status: "pending_review" }, 201));
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock });

    const state = await submitAndPublishRequest(input, client, () => "key-1");

    expect(state.status).toBe("pending_review");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(submissionErrorMessage(state)).toBeNull();
  });

  it("公開だけ失敗したら、作成済みの依頼を持ったまま知らせる", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(created, 201))
      .mockResolvedValueOnce(errorResponse(503, "SERVICE_UNAVAILABLE"));
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock });

    const state = await submitAndPublishRequest(input, client, () => "key-1");

    expect(state.status).toBe("created_unpublished");
    expect(state.request?.id).toBe("request-1");
    expect(submissionErrorMessage(state)).toContain("公開できませんでした");
  });

  it("禁止された内容は理由付きで失敗にする", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(errorResponse(422, "PROHIBITED_REQUEST"));
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock });

    const state = await submitAndPublishRequest(input, client, () => "key-1");

    expect(state).toMatchObject({ status: "failed", reason: "prohibited", request: null });
    expect(submissionErrorMessage(state)).toContain("お受けできません");
  });

  it.each([
    [422, "VALIDATION_ERROR", "validation_error"],
    [409, "IDEMPOTENCY_CONFLICT", "conflict"],
    [500, "INTERNAL_ERROR", "error"],
  ])("HTTP %s (%s) は %s として失敗にする", async (status, code, reason) => {
    const fetchMock = vi.fn().mockResolvedValueOnce(errorResponse(status, code));
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock });

    const state = await submitAndPublishRequest(input, client, () => "key-1");

    expect(state).toMatchObject({ status: "failed", reason });
    expect(submissionErrorMessage(state)).toBeTruthy();
  });
});
