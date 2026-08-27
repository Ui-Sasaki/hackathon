import { AuthClient, AuthProfile, AuthResult } from "./client";

export type SessionSnapshot = {
  profile: AuthProfile | null;
  status: "authenticated" | "unauthenticated";
};

export async function restoreSession(client: AuthClient): Promise<SessionSnapshot> {
  const profile = await client.restore();
  return { profile, status: profile ? "authenticated" : "unauthenticated" };
}

export async function authenticate(
  client: AuthClient,
  action: () => Promise<AuthResult>,
): Promise<{ result: AuthResult; snapshot?: SessionSnapshot }> {
  const result = await action();
  if (!result.ok) return { result };
  const profile = await client.getProfile();
  return { result, snapshot: { profile, status: "authenticated" } };
}

export async function destroySession(client: AuthClient): Promise<SessionSnapshot> {
  await client.signOut();
  return { profile: null, status: "unauthenticated" };
}
