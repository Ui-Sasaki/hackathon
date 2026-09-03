import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../api/client";
import {
  getRequest,
  listPublicRequests,
  requestListErrorMessage,
  tagsForCategory,
  toRequestCard,
  type PublicRequest,
} from "./client";

const REQUEST: PublicRequest = {
  id: "5fcfec7f-a8b0-58d4-931e-593d60355ee3",
  title: "犬の散歩をお願いしたい",
  description: "体調不良のため、小型犬の散歩を30分お願いしたいです。",
  category: "pet_support",
  areaLabel: "大学周辺・約1km",
  distanceKm: 1.0,
  scheduledAt: "2026-08-18T10:00:00+09:00",
  estimatedMinutes: 30,
  requiredHelpers: 1,
  acceptedHelpers: 0,
  status: "published",
  warnings: [],
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

describe("公開依頼の一覧取得", () => {
  it("一覧とカーソルを返す", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ items: [REQUEST], nextCursor: null }));

    const page = await listPublicRequests({}, clientWith(fetchMock));

    expect(page.items).toHaveLength(1);
    expect(page.items[0].id).toBe(REQUEST.id);
    expect(page.nextCursor).toBeNull();
    expect(fetchMock.mock.calls[0][0]).toBe("http://api.test/requests");
  });

  it("検索条件をクエリとして送る", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ items: [], nextCursor: null }));

    await listPublicRequests(
      { areaCode: "AREA-001", category: "pet_support" },
      clientWith(fetchMock),
    );

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("areaCode=AREA-001");
    expect(url).toContain("category=pet_support");
  });

  it("セッションCookieを送る", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ items: [], nextCursor: null }));

    await listPublicRequests({}, clientWith(fetchMock));

    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
  });

  it("依頼IDで詳細を取得する", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(REQUEST));

    const item = await getRequest(REQUEST.id, clientWith(fetchMock));

    expect(item.title).toBe(REQUEST.title);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      `http://api.test/requests/${REQUEST.id}`,
    );
  });
});

describe("カード表示への変換", () => {
  it("APIの依頼をカードの形へ変換する", () => {
    const card = toRequestCard(REQUEST);

    expect(card).toEqual({
      id: REQUEST.id,
      title: "犬の散歩をお願いしたい",
      description: REQUEST.description,
      location: "大学周辺・約1km",
      distance: "1km",
      deadline: "8/18",
      meta: "約30分・1人募集",
      tags: ["#動物", "#散歩"],
    });
  });

  it("距離が不明なら空文字にする", () => {
    expect(toRequestCard({ ...REQUEST, distanceKm: null }).distance).toBe("");
  });

  it("解釈できない日時は空文字にする", () => {
    expect(toRequestCard({ ...REQUEST, scheduledAt: "いつでも" }).deadline).toBe("");
  });

  it("年齢・性別は含めない", () => {
    const card = toRequestCard(REQUEST);
    expect(Object.keys(card)).not.toContain("age");
    expect(Object.keys(card)).not.toContain("gender");
  });

  it.each([
    ["pet_support", ["#動物", "#散歩"]],
    ["snow_removal", ["#力仕事"]],
    ["shopping", ["#買い物"]],
    ["unknown_category", ["#その他"]],
  ])("カテゴリ %s をタグへ変換する", (category, tags) => {
    expect(tagsForCategory(category)).toEqual(tags);
  });
});

describe("失敗の表示", () => {
  it("通信失敗を利用者向けの文言にする", () => {
    expect(requestListErrorMessage(new TypeError("Failed to fetch"))).toContain(
      "依頼を読み込めませんでした",
    );
  });
});
