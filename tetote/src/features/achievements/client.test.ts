import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../api/client";
import { generateAchievement, publishAchievement } from "./client";

const achievement = { id: "achievement-1", generatedText: "地域活動を支援しました" };

describe("achievement client", () => {
  it("generates privately and publishes only after explicit approval", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify(achievement), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock as never });

    await generateAchievement("match-1", client);
    await publishAchievement("achievement-1", "members", client);

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ matchId: "match-1", visibility: "private" });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      achievementId: "achievement-1", visibility: "members", approved: true,
    });
  });
});
