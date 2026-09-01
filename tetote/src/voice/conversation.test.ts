import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../api/client";
import {
  appendAnswer,
  MAX_QUESTION_ROUNDS,
  nextConversationStep,
} from "./conversation";

const MASKING_PREVIEW = {
  maskedText: "庭の草むしりを手伝ってほしい",
  detections: [],
  hasDetections: false,
  ruleVersion: "pii-mask-v1",
  status: "masking_confirmation_required",
  requiresMaskingConfirmation: true,
  message: "確認してください",
};

const STRUCTURED_BASE = {
  title: "庭の草むしり",
  description: "庭の草むしりを手伝ってほしい",
  category: "gardening",
  scheduledAt: null,
  estimatedMinutes: 60,
  approximateArea: null,
  requiredHelpers: 1,
  itemsToBring: [],
  riskLevel: "low",
  riskCandidates: [],
  missingFields: [],
  warnings: [],
  masking: { detections: [], ruleVersion: "pii-mask-v1", confirmed: true },
  status: "draft",
  requiresConfirmation: true,
  autoPublished: false,
  additionalQuestion: null,
  metadata: {
    modelName: "test-model",
    promptVersion: "request-structure-v1",
    processedAt: "2026-09-01T00:00:00Z",
  },
  request: { task: "庭の草むしり", location: null, duration: null, deadline: null, notes: null },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function clientWith(fetchMock: ReturnType<typeof vi.fn>): ApiClient {
  return new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock as never });
}

describe("音声入力の会話ループ", () => {
  it("不足情報があれば追加質問を返す", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(MASKING_PREVIEW))
      .mockResolvedValueOnce(
        jsonResponse({
          ...STRUCTURED_BASE,
          additionalQuestion: "どこでお願いしたいですか？",
        }),
      );

    const step = await nextConversationStep("庭の草むしり", 0, clientWith(fetchMock));

    expect(step).toEqual({ type: "question", question: "どこでお願いしたいですか？" });
  });

  it("不足がなければ確認画面へ進む", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(MASKING_PREVIEW))
      .mockResolvedValueOnce(jsonResponse(STRUCTURED_BASE));

    const step = await nextConversationStep("庭の草むしり", 0, clientWith(fetchMock));

    expect(step).toEqual({ type: "proceed" });
  });

  it("質問の上限に達したらAPIを呼ばずに進む", async () => {
    const fetchMock = vi.fn();

    const step = await nextConversationStep(
      "庭の草むしり",
      MAX_QUESTION_ROUNDS,
      clientWith(fetchMock),
    );

    expect(step).toEqual({ type: "proceed" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("マスキングAPIが失敗しても行き止まりにしない", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    const step = await nextConversationStep("庭の草むしり", 0, clientWith(fetchMock));

    expect(step).toEqual({ type: "proceed" });
  });

  it("構造化APIが停止していても確認画面へ進む", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(MASKING_PREVIEW))
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: "STRUCTURE_SERVICE_UNAVAILABLE", message: "x" } },
          503,
        ),
      );

    const step = await nextConversationStep("庭の草むしり", 0, clientWith(fetchMock));

    expect(step).toEqual({ type: "proceed" });
  });

  it("構造化へはマスク済みテキストを confirmed で送る", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          ...MASKING_PREVIEW,
          maskedText: "連絡先は[電話番号]です",
          hasDetections: true,
        }),
      )
      .mockResolvedValueOnce(jsonResponse(STRUCTURED_BASE));

    await nextConversationStep("連絡先は090-1234-5678です", 0, clientWith(fetchMock));

    const sent = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(sent.text).toBe("連絡先は[電話番号]です");
    expect(sent.maskingConfirmed).toBe(true);
  });
});

describe("回答の継ぎ足し", () => {
  it("これまでの内容へ改行で足す", () => {
    expect(appendAnswer("庭の草むしり", "場所は自宅の庭です")).toBe(
      "庭の草むしり\n場所は自宅の庭です",
    );
  });

  it("最初の発話はそのまま使う", () => {
    expect(appendAnswer("", "庭の草むしり")).toBe("庭の草むしり");
  });

  it("空の回答は無視する", () => {
    expect(appendAnswer("庭の草むしり", "   ")).toBe("庭の草むしり");
  });
});
