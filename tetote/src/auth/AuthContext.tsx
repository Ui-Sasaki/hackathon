import {
  createContext,
  PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  AuthClient,
  AuthProfile,
  AuthResult,
  ProfileUpdate,
  browserAuthClient,
  initializeAuthClient,
} from "./client";
import { authenticate, destroySession, restoreSession } from "./session";

type AuthStatus = "loading" | "authenticated" | "unauthenticated" | "error";

type AuthContextValue = {
  status: AuthStatus;
  profile: AuthProfile | null;
  signUp(email: string, password: string): Promise<AuthResult>;
  signIn(email: string, password: string): Promise<AuthResult>;
  signOut(): Promise<void>;
  refreshProfile(): Promise<AuthProfile>;
  updateProfile(update: ProfileUpdate): Promise<AuthProfile>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  children,
  client = browserAuthClient,
}: PropsWithChildren<{ client?: AuthClient }>) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [profile, setProfile] = useState<AuthProfile | null>(null);

  const clearSession = useCallback(() => {
    setProfile(null);
    setStatus("unauthenticated");
  }, []);

  useEffect(() => {
    let active = true;
    initializeAuthClient(clearSession);
    restoreSession(client)
      .then((snapshot) => {
        if (!active) return;
        setProfile(snapshot.profile);
        setStatus(snapshot.status);
      })
      .catch(() => {
        if (!active) return;
        setProfile(null);
        setStatus("error");
      });
    return () => {
      active = false;
    };
  }, [clearSession, client]);

  const establishSession = useCallback(
    async (action: () => Promise<AuthResult>): Promise<AuthResult> => {
      const authenticated = await authenticate(client, action);
      if (authenticated.snapshot) {
        setProfile(authenticated.snapshot.profile);
        setStatus(authenticated.snapshot.status);
      }
      return authenticated.result;
    },
    [client],
  );

  const refreshProfile = useCallback(async () => {
    const nextProfile = await client.getProfile();
    setProfile(nextProfile);
    setStatus("authenticated");
    return nextProfile;
  }, [client]);

  const updateProfile = useCallback(async (update: ProfileUpdate) => {
    const nextProfile = await client.updateProfile(update);
    setProfile(nextProfile);
    return nextProfile;
  }, [client]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      profile,
      signUp: (email, password) =>
        establishSession(() => client.signUp(email, password)),
      signIn: (email, password) =>
        establishSession(() => client.signIn(email, password)),
      signOut: async () => {
        try {
          const snapshot = await destroySession(client);
          setProfile(snapshot.profile);
          setStatus(snapshot.status);
        } finally {
          clearSession();
        }
      },
      refreshProfile,
      updateProfile,
    }),
    [clearSession, client, establishSession, profile, refreshProfile, status, updateProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
