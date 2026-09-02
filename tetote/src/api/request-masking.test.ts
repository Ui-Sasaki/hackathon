import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiAuthenticationError, ApiError, ApiNetworkError } from "./errors";
import {
  canProceedAfterMasking,
  confirmMaskingPreview,
  previewRequestMasking,
  type MaskingPreview,
} from "./request-masking";

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const preview: MaskingPreview = {
  maskedText: "連絡先は[メールアドレス]です",
  detections: [{ type: "email", placeholder: "[メールアドレス]", count: 1 }],
  hasDetections: true,
  ruleVersion: "pii-v1",
  status: "masking_confirmation_required",
  requiresMaskingConfirmation: true,
  message: "マスキング結果を確認してください",
};

describe("TODO 09: masking preview API", () => {
  it("sends only the request text and keeps the complete preview unconfirmed", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, preview));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await previewRequestMasking("連絡先はhanako@example.jpです", client);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      text: "連絡先はhanako@example.jpです",
    });
    expect(state).toEqual({ status: "ready", preview, confirmed: false, error: null });
    expect(canProceedAfterMasking(state)).toBe(false);
  });

  it("allows the next step only after explicit confirmation", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(jsonResponse(200, preview)),
    });
    const state = await previewRequestMasking("依頼本文です", client);

    const confirmed = confirmMaskingPreview(state);

    expect(confirmed).toMatchObject({
      status: "confirmed",
      confirmed: true,
      preview: {
        maskedText: preview.maskedText,
        detections: preview.detections,
        ruleVersion: preview.ruleVersion,
      },
    });
    expect(canProceedAfterMasking(confirmed)).toBe(true);
  });

  it.each([
    [401, "AUTHENTICATION_REQUIRED", ApiAuthenticationError],
    [422, "VALIDATION_ERROR", ApiError],
  ] as const)("reflects a %i API error", async (status, code, errorType) => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockResolvedValue(
        jsonResponse(status, {
          error: { code, message: "処理できません", details: {}, requestId: "trace_masking" },
        }),
      ),
    });

    const state = await previewRequestMasking("依頼本文です", client);

    expect(state.status).toBe("error");
    if (state.status === "error") {
      expect(state.error).toBeInstanceOf(errorType);
      expect(state.error).toMatchObject({ status, code });
    }
    expect(canProceedAfterMasking(state)).toBe(false);
  });

  it("reflects a network failure and keeps the next step blocked", async () => {
    const client = new ApiClient({
      baseUrl: "https://api.example.test",
      fetch: vi.fn().mockRejectedValue(new TypeError("offline")),
    });

    const state = await previewRequestMasking("依頼本文です", client);

    expect(state.status).toBe("error");
    if (state.status === "error") expect(state.error).toBeInstanceOf(ApiNetworkError);
    expect(canProceedAfterMasking(state)).toBe(false);
  });
});
