import SuperTokens from "supertokens-web-js";
import EmailPassword, {
  signIn as superTokensSignIn,
  signUp as superTokensSignUp,
} from "supertokens-web-js/recipe/emailpassword";
import Session, {
  doesSessionExist,
  signOut as superTokensSignOut,
} from "supertokens-web-js/recipe/session";

export type VerificationStatus =
  | "unverified"
  | "pending"
  | "approved"
  | "rejected";

export type AuthProfile = {
  id: string;
  displayName: string;
  role: "member" | "admin" | "verifier";
  emailVerified: boolean;
  verificationStatus: VerificationStatus;
  status: "active" | "suspended";
  areaCode: string | null;
};

export type ProfileUpdate = {
  displayName?: string;
  areaCode?: string;
};

export type AuthResult =
  | { ok: true }
  | { ok: false; message: string };

export interface AuthClient {
  restore(): Promise<AuthProfile | null>;
  signUp(email: string, password: string): Promise<AuthResult>;
  signIn(email: string, password: string): Promise<AuthResult>;
  signOut(): Promise<void>;
  getProfile(): Promise<AuthProfile>;
  updateProfile(update: ProfileUpdate): Promise<AuthProfile>;
}

const apiDomain = (process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

let initialized = false;

export function initializeAuthClient(onUnauthorized?: () => void): void {
  if (initialized || typeof window === "undefined") return;

  SuperTokens.init({
    appInfo: {
      appName: "たすけの輪",
      apiDomain,
      apiBasePath: "/auth",
    },
    recipeList: [
      EmailPassword.init(),
      Session.init({
        onHandleEvent: (event) => {
          if (
            event.action === "UNAUTHORISED" &&
            event.sessionExpiredOrRevoked
          ) {
            onUnauthorized?.();
          }
        },
      }),
    ],
  });
  initialized = true;
}

async function getProfile(): Promise<AuthProfile> {
  const response = await fetch(`${apiDomain}/profile`, {
    credentials: "include",
    headers: { Accept: "application/json" },
  });

  if (response.status === 401) {
    throw new AuthExpiredError();
  }
  if (!response.ok) {
    throw new Error("プロフィールを取得できませんでした");
  }
  return (await response.json()) as AuthProfile;
}

export class ProfileValidationError extends Error {
  constructor(message = "入力内容を確認してください") {
    super(message);
    this.name = "ProfileValidationError";
  }
}

async function updateProfile(update: ProfileUpdate): Promise<AuthProfile> {
  const response = await fetch(`${apiDomain}/profile`, {
    method: "PATCH",
    credentials: "include",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });

  if (response.status === 401) throw new AuthExpiredError();
  if (response.status === 422) throw new ProfileValidationError();
  if (!response.ok) throw new Error("プロフィールを更新できませんでした");
  return (await response.json()) as AuthProfile;
}

function fieldErrorMessage(
  fields: { id: string; error: string }[],
): string {
  return fields[0]?.error ?? "入力内容を確認してください";
}

export class AuthExpiredError extends Error {
  constructor() {
    super("セッションの有効期限が切れました。もう一度ログインしてください");
    this.name = "AuthExpiredError";
  }
}

export const browserAuthClient: AuthClient = {
  async restore() {
    if (!(await doesSessionExist())) return null;
    try {
      return await getProfile();
    } catch (error) {
      if (error instanceof AuthExpiredError) return null;
      throw error;
    }
  },

  async signUp(email, password) {
    const result = await superTokensSignUp({
      formFields: [
        { id: "email", value: email },
        { id: "password", value: password },
      ],
    });
    if (result.status === "OK") return { ok: true };
    if (result.status === "FIELD_ERROR") {
      return { ok: false, message: fieldErrorMessage(result.formFields) };
    }
    return { ok: false, message: result.reason };
  },

  async signIn(email, password) {
    const result = await superTokensSignIn({
      formFields: [
        { id: "email", value: email },
        { id: "password", value: password },
      ],
    });
    if (result.status === "OK") return { ok: true };
    if (result.status === "FIELD_ERROR") {
      return { ok: false, message: fieldErrorMessage(result.formFields) };
    }
    if (result.status === "WRONG_CREDENTIALS_ERROR") {
      return { ok: false, message: "メールアドレスまたはパスワードが違います" };
    }
    return { ok: false, message: result.reason };
  },

  async signOut() {
    await superTokensSignOut();
  },

  getProfile,
  updateProfile,
};

export function resetAuthClientForTests(): void {
  initialized = false;
}
