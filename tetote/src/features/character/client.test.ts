import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../api/client";
import {
  characterAssetKey,
  characterProgressErrorMessage,
  characterProgressLoadingState,
  evolutionLabel,
  getCharacterProgress,
  progressPercent,
  type CharacterProgress,
} from "./client";

const progress: CharacterProgress = {
  userId: "usr_207",
  helpCount: 2,
  currentPoints: 175,
  stage: 2,
  maxStage: 3,
  characterId: "c2",
  nextStagePoints: 350,
  pointsUntilNextStage: 175,
  progressRatio: 0.125,
  ruleVersion: "v1",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("キャラクター進捗の取得", () => {
  it("読み込み中の状態を持つ", () => {
    expect(characterProgressLoadingState()).toEqual({ status: "loading", progress: null, error: null });
  });

  it("GET /character-progress の結果をそのまま返す", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(progress));
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock });

    await expect(getCharacterProgress(client)).resolves.toEqual({
      status: "ready",
      progress,
      error: null,
    });
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.test/character-progress");
    expect(options.method).toBe("GET");
  });

  it("失敗したら error 状態にして、利用者向けの文言を出せる", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ error: { code: "AUTHENTICATION_REQUIRED", message: "x", details: {}, requestId: "r" } }, 401),
    );
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock });

    const state = await getCharacterProgress(client);

    expect(state.status).toBe("error");
    expect(characterProgressErrorMessage(state.error)).toContain("ログイン");
    expect(characterProgressErrorMessage(new Error("boom"))).toContain("読み込めません");
  });
});

describe("表示用の変換", () => {
  it("進捗バーの割合を0〜100に丸める", () => {
    expect(progressPercent(progress)).toBe(13);
    expect(progressPercent({ ...progress, progressRatio: 1.7 })).toBe(100);
    expect(progressPercent({ ...progress, progressRatio: -1 })).toBe(0);
    expect(progressPercent(null)).toBe(0);
  });

  it("進化までの文言", () => {
    expect(evolutionLabel(progress)).toBe("進化まであと175pt");
    expect(evolutionLabel({ ...progress, nextStagePoints: null, pointsUntilNextStage: 0 })).toBe(
      "最終段階まで進化しました",
    );
    expect(evolutionLabel(null)).toBe("進化まであと…pt");
  });

  it("段階ごとの画像の鍵を返し、不明なら最初の姿にする", () => {
    expect(characterAssetKey("c1")).toBe("c1");
    expect(characterAssetKey("c2")).toBe("c2");
    expect(characterAssetKey("c3")).toBe("c3");
    expect(characterAssetKey("c9")).toBe("c1");
    expect(characterAssetKey(null)).toBe("c1");
    expect(characterAssetKey(undefined)).toBe("c1");
  });
});
