import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiAuthenticationError, ApiError, ApiNetworkError } from "./errors";
import type { MaskingPreviewState } from "./request-masking";
import { structureConfirmedRequest, updateStructuredDraft } from "./request-structuring";

const response = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const confirmedMasking: MaskingPreviewState = {
  status: "confirmed",
  confirmed: true,
  error: null,
  preview: {
    maskedText: "連絡先は[電話番号]です。犬の散歩をお願いします",
    detections: [{ type: "phone", placeholder: "[電話番号]", count: 1 }],
    hasDetections: true,
    ruleVersion: "pii-v1",
    status: "masking_confirmation_required",
    requiresMaskingConfirmation: true,
    message: "確認してください",
  },
};

const structuredResponse = {
  title: "犬の散歩",
  description: confirmedMasking.preview.maskedText,
  category: "pet_support",
  scheduledAt: null,
  estimatedMinutes: 30,
  approximateArea: null,
  requiredHelpers: 1,
  itemsToBring: [],
  riskLevel: "low",
  riskCandidates: [],
  missingFields: ["scheduledAt"],
  warnings: [],
  masking: { detections: [], ruleVersion: "pii-v1", confirmed: true },
  status: "draft",
  requiresConfirmation: true,
  autoPublished: false,
  additionalQuestion: "希望日時を教えてください",
  metadata: { modelName: "local", promptVersion: "v1", processedAt: "2026-08-31T00:00:00Z" },
};

describe("TODO 10: request structuring API", () => {
  it("blocks the API until the masking preview is explicitly confirmed", async () => {
    const fetchMock = vi.fn();
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await structureConfirmedRequest(null, client);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(state.status).toBe("error");
  });

  it("sends only confirmed masked text and creates an editable, unpublished draft", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, structuredResponse));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await structureConfirmedRequest(confirmedMasking, client);

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      text: confirmedMasking.preview.maskedText,
      maskingConfirmed: true,
    });
    expect(fetchMock.mock.calls[0][1].body).not.toContain("090-");
    expect(state).toMatchObject({
      status: "draft",
      additionalQuestion: "希望日時を教えてください",
      draft: { title: "犬の散歩", description: confirmedMasking.preview.maskedText },
    });

    const edited = updateStructuredDraft(state, { title: "小型犬の散歩" });
    expect(edited.draft?.title).toBe("小型犬の散歩");
  });

  it.each([502, 503])("keeps the input in an editable manual draft after %i", async (status) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(status, {
        error: { code: "STRUCTURE_UNAVAILABLE", message: "利用できません", details: {}, requestId: "trace" },
      })),
    });

    const state = await structureConfirmedRequest(confirmedMasking, client);

    expect(state.status).toBe("manual");
    expect(state.draft?.description).toBe(confirmedMasking.preview.maskedText);
    expect(state.error).toBeInstanceOf(ApiError);
  });

  it("keeps the input in an editable manual draft after a network failure", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockRejectedValue(new TypeError("offline")),
    });

    const state = await structureConfirmedRequest(confirmedMasking, client);

    expect(state).toMatchObject({ status: "manual", originalText: confirmedMasking.preview.maskedText });
    expect(state.error).toBeInstanceOf(ApiNetworkError);
  });

  it.each([
    [401, ApiAuthenticationError],
    [422, ApiError],
  ] as const)("keeps status %i as a blocking shared API error", async (status, errorType) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(response(status, {
        error: { code: "REQUEST_REJECTED", message: "処理できません", details: {}, requestId: "trace" },
      })),
    });

    const state = await structureConfirmedRequest(confirmedMasking, client);

    expect(state.status).toBe("error");
    expect(state.error).toBeInstanceOf(errorType);
  });
});
