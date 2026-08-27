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

export class ApiAuthenticationError extends Error {
  readonly status = 401;

  constructor(message = "セッションの有効期限が切れました。もう一度ログインしてください") {
    super(message);
    this.name = "ApiAuthenticationError";
  }
}
