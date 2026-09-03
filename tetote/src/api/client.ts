import { apiConfigurationProblem, getApiBaseUrl } from "./config";
import {
  ApiConfigurationError,
  ApiNetworkError,
  ApiTimeoutError,
  toApiError,
} from "./errors";

export type ApiRequestOptions = Omit<RequestInit, "body" | "credentials" | "headers"> & {
  body?: unknown;
  /** JSONへ変換せずそのまま送る本文。画像などのバイナリに使う。 */
  rawBody?: BodyInit;
  /** rawBody を送るときの Content-Type。 */
  contentType?: string;
  headers?: HeadersInit;
  timeoutMs?: number;
  /** 通信に失敗したときの再試行回数。既定はGETだけ再試行する。 */
  retries?: number;
  /** 再試行までの待ち時間。テストから短縮できるようにしている。 */
  retryDelayMs?: number;
};

export type ApiClientOptions = {
  baseUrl?: string;
  fetch?: typeof fetch;
  timeoutMs?: number;
};

// 無料枠のホスティングは停止状態から起きるのに時間がかかる。
// 10秒では正常な構成でも初回アクセスが失敗するため、余裕を取る。
const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_RETRY_DELAY_MS = 1_000;

// 再試行は取得系だけに限る。作成・更新を再送すると二重登録になり得る。
const RETRYABLE_METHODS = new Set(["GET", "HEAD"]);
const DEFAULT_GET_RETRIES = 2;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchOverride?: typeof fetch;
  private readonly timeoutMs: number;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? getApiBaseUrl()).replace(/\/+$/, "");
    this.fetchOverride = options.fetch;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  }

  get<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  post<T>(path: string, body?: unknown, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "POST", body });
  }

  patch<T>(path: string, body?: unknown, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "PATCH", body });
  }

  put<T>(path: string, body?: unknown, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "PUT", body });
  }

  delete<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "DELETE" });
  }

  async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    const method = (options.method ?? "GET").toUpperCase();
    const retries =
      options.retries ?? (RETRYABLE_METHODS.has(method) ? DEFAULT_GET_RETRIES : 0);
    const retryDelayMs = options.retryDelayMs ?? DEFAULT_RETRY_DELAY_MS;

    for (let attempt = 0; ; attempt += 1) {
      try {
        return await this.send<T>(path, options);
      } catch (error) {
        // 応答が返ってきた失敗（401や422など）は再試行しても結果が変わらない。
        if (!(error instanceof ApiNetworkError) || attempt >= retries) {
          throw error;
        }
        // 停止していたサーバーが起き上がるのを待つ。待ち時間は毎回伸ばす。
        await delay(retryDelayMs * (attempt + 1));
      }
    }
  }

  private async send<T>(path: string, options: ApiRequestOptions): Promise<T> {
    const controller = new AbortController();
    const timeoutMs = options.timeoutMs ?? this.timeoutMs;
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    const { body, rawBody, contentType, headers: headerInit, ...init } = options;
    const headers = new Headers(headerInit);
    headers.set("Accept", "application/json");
    if (rawBody !== undefined) {
      headers.set("Content-Type", contentType ?? "application/octet-stream");
    } else if (body !== undefined) {
      headers.set("Content-Type", "application/json");
    }

    try {
      const fetcher = this.fetchOverride ?? globalThis.fetch;
      const response = await fetcher(`${this.baseUrl}${path}`, {
        ...init,
        body:
          rawBody !== undefined
            ? rawBody
            : body === undefined
              ? undefined
              : JSON.stringify(body),
        credentials: "include",
        headers,
        signal: controller.signal,
      });
      if (!response.ok) throw await toApiError(response);
      if (response.status === 204) return undefined as T;
      return (await response.json()) as T;
    } catch (error) {
      // 接続先の設定漏れは通信障害と原因が違うため、区別して伝える。
      const problem = apiConfigurationProblem();
      if (
        problem &&
        (error instanceof TypeError ||
          (error instanceof Error && error.name === "AbortError"))
      ) {
        throw new ApiConfigurationError(problem, { cause: error });
      }
      if (error instanceof Error && error.name === "AbortError") {
        throw new ApiTimeoutError(undefined, { cause: error });
      }
      if (error instanceof TypeError) {
        throw new ApiNetworkError(undefined, { cause: error });
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }
}

export const apiClient = new ApiClient();

/**
 * 停止しているサーバーを先に起こす。画面を開いた時点で呼び、
 * 利用者が登録や送信を押したときには起動が終わっている状態にする。
 */
export async function warmUpApi(
  client: ApiClient = apiClient,
  options: Pick<ApiRequestOptions, "retries" | "retryDelayMs"> = {},
): Promise<boolean> {
  try {
    await client.get("/health", { retries: 3, ...options });
    return true;
  } catch {
    return false;
  }
}
