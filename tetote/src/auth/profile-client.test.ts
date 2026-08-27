import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthExpiredError, browserAuthClient, ProfileValidationError } from "./client";

const response = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("profile client", () => {
  it("sends the existing frontend profile fields", async () => {
    const profile = { id: "user-1", displayName: "花子", role: "member", emailVerified: false, verificationStatus: "unverified", areaCode: "東京都", status: "active" };
    const fetchMock = vi.fn().mockResolvedValue(response(200, profile));
    vi.stubGlobal("fetch", fetchMock);
    const update = {
      displayName: "花子",
      region: "東京都",
      age: "22",
      notes: "犬の扱いに慣れています",
      helperType: "student" as const,
      university: "テトテ大学",
      faculty: "地域学部",
      schoolYear: "3年",
    };
    await browserAuthClient.updateProfile(update);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(update);
  });

  it("exposes validation and authentication failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(422)));
    await expect(browserAuthClient.updateProfile({ displayName: "" })).rejects.toBeInstanceOf(ProfileValidationError);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(401)));
    await expect(browserAuthClient.updateProfile({ displayName: "花子" })).rejects.toBeInstanceOf(AuthExpiredError);
  });
});
