import { AuthExpiredError, ProfileValidationError } from "./client";

export type ProfileRequestError = "unauthorized" | "validation" | "network";

export function profileErrorKind(error: unknown): ProfileRequestError {
  if (error instanceof AuthExpiredError) return "unauthorized";
  if (error instanceof ProfileValidationError) return "validation";
  return "network";
}

export function profileErrorMessage(kind: ProfileRequestError): string {
  if (kind === "unauthorized") return "ログインし直してください";
  if (kind === "validation") return "プロフィールの入力内容を確認してください";
  return "通信に失敗しました。時間をおいて再度お試しください";
}
