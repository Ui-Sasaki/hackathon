export class ApiNetworkError extends Error {
  constructor(message = "APIへ接続できませんでした", options?: ErrorOptions) {
    super(message, options);
    this.name = "ApiNetworkError";
  }
}

export class ApiTimeoutError extends ApiNetworkError {
  constructor(message = "APIへの接続がタイムアウトしました", options?: ErrorOptions) {
    super(message, options);
    this.name = "ApiTimeoutError";
  }
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor({
    status,
    code,
    message,
    details = {},
    requestId = null,
  }: {
    status: number;
    code: string;
    message: string;
    details?: unknown;
    requestId?: string | null;
  }) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export class ApiAuthenticationError extends ApiError {
  constructor({
    code = "AUTHENTICATION_REQUIRED",
    message = "セッションの有効期限が切れました。もう一度ログインしてください",
    details = {},
    requestId = null,
  }: {
    code?: string;
    message?: string;
    details?: unknown;
    requestId?: string | null;
  } = {}) {
    super({ status: 401, code, message, details, requestId });
    this.name = "ApiAuthenticationError";
  }
}

const fallbackCodes: Record<number, string> = {
  401: "AUTHENTICATION_REQUIRED",
  403: "FORBIDDEN",
  404: "NOT_FOUND",
  409: "CONFLICT",
  422: "VALIDATION_ERROR",
  500: "INTERNAL_SERVER_ERROR",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.clone().json();
  } catch {
    body = null;
  }

  const error = isRecord(body) && isRecord(body.error) ? body.error : null;
  const code = typeof error?.code === "string" ? error.code : fallbackCodes[response.status] ?? "HTTP_ERROR";
  const message = typeof error?.message === "string" ? error.message : "通信処理に失敗しました";
  const details = error && "details" in error ? error.details : {};
  const requestId = typeof error?.requestId === "string" ? error.requestId : null;

  if (response.status === 401) {
    return new ApiAuthenticationError({ code, message, details, requestId });
  }
  return new ApiError({ status: response.status, code, message, details, requestId });
}
