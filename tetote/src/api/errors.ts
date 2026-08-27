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
