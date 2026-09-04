import { apiClient, type ApiClient } from "../../api/client";

export type AchievementVisibility = "private" | "members" | "public";

export type Achievement = {
  id: string;
  userId: string;
  matchId: string;
  generatedText: string;
  facts: Record<string, unknown>;
  visibility: AchievementVisibility;
  status: "generated" | "approved";
  modelName: string;
  promptVersion: string;
  generatedAt: string;
  approvedAt: string | null;
};

export function generateAchievement(
  matchId: string,
  client: ApiClient = apiClient,
): Promise<Achievement> {
  return client.post<Achievement>("/achievements/generate", {
    matchId,
    visibility: "private",
  });
}

export function publishAchievement(
  achievementId: string,
  visibility: AchievementVisibility,
  client: ApiClient = apiClient,
): Promise<Achievement> {
  return client.patch<Achievement>("/achievements/visibility", {
    achievementId,
    visibility,
    approved: true,
  });
}
