import { describe, expect, it, vi } from "vitest";

import { AuthClient, AuthProfile } from "./client";
import { authenticate, destroySession, restoreSession } from "./session";

const profile: AuthProfile = {
  id: "user-1",
  displayName: "利用者",
  role: "member",
  emailVerified: false,
  verificationStatus: "unverified",
  status: "active",
  areaCode: null,
};

function fakeClient(overrides: Partial<AuthClient> = {}): AuthClient {
  return {
    restore: vi.fn().mockResolvedValue(profile),
    signUp: vi.fn().mockResolvedValue({ ok: true }),
    signIn: vi.fn().mockResolvedValue({ ok: true }),
    signOut: vi.fn().mockResolvedValue(undefined),
    getProfile: vi.fn().mockResolvedValue(profile),
    updateProfile: vi.fn().mockResolvedValue(profile),
    ...overrides,
  };
}

describe("authentication session lifecycle", () => {
  it("restores a cookie session and keeps verification states separate", async () => {
    const snapshot = await restoreSession(fakeClient());
    expect(snapshot.status).toBe("authenticated");
    expect(snapshot.profile?.emailVerified).toBe(false);
    expect(snapshot.profile?.verificationStatus).toBe("unverified");
  });

  it("treats an expired session as unauthenticated without retrying", async () => {
    const restore = vi.fn().mockResolvedValue(null);
    const snapshot = await restoreSession(fakeClient({ restore }));
    expect(snapshot).toEqual({ profile: null, status: "unauthenticated" });
    expect(restore).toHaveBeenCalledTimes(1);
  });

  it("keeps restore failures distinct from an expired session", async () => {
    const failure = new Error("profile service unavailable");
    const client = fakeClient({ restore: vi.fn().mockRejectedValue(failure) });

    await expect(restoreSession(client)).rejects.toBe(failure);
  });

  it.each(["signUp", "signIn"] as const)(
    "establishes a server-backed session after %s",
    async (method) => {
      const client = fakeClient();
      const authenticated = await authenticate(client, () =>
        client[method]("member@example.com", "password123"),
      );
      expect(authenticated.result.ok).toBe(true);
      expect(authenticated.snapshot?.status).toBe("authenticated");
      expect(client.getProfile).toHaveBeenCalledTimes(1);
    },
  );

  it("does not fetch a profile when credentials are rejected", async () => {
    const client = fakeClient({
      signIn: vi.fn().mockResolvedValue({ ok: false, message: "認証失敗" }),
    });
    const authenticated = await authenticate(client, () =>
      client.signIn("member@example.com", "wrong-password"),
    );
    expect(authenticated.snapshot).toBeUndefined();
    expect(client.getProfile).not.toHaveBeenCalled();
  });

  it("revokes the server session before clearing local auth state", async () => {
    const client = fakeClient();
    const snapshot = await destroySession(client);
    expect(client.signOut).toHaveBeenCalledTimes(1);
    expect(snapshot).toEqual({ profile: null, status: "unauthenticated" });
  });
});
