import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthExpiredError, browserAuthClient, ProfileValidationError } from "./client";

const response = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("profile client", () => {
  it("sends only the editable profile fields", async () => {
    const profile = { id: "user-1", displayName: "花子", role: "member", emailVerified: false, verificationStatus: "unverified", areaCode: "東京都", status: "active" };
    const fetchMock = vi.fn().mockResolvedValue(response(200, profile));
    vi.stubGlobal("fetch", fetchMock);
    await browserAuthClient.updateProfile({ displayName: "花子", areaCode: "東京都" });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ displayName: "花子", areaCode: "東京都" });
  });

  it("exposes validation and authentication failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(422)));
    await expect(browserAuthClient.updateProfile({ displayName: "" })).rejects.toBeInstanceOf(ProfileValidationError);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(response(401)));
    await expect(browserAuthClient.updateProfile({ displayName: "花子" })).rejects.toBeInstanceOf(AuthExpiredError);
  });
});
