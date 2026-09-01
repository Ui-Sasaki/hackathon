import { getApiBaseUrl } from "./config";
import { ApiNetworkError, ApiTimeoutError, toApiError } from "./errors";

export type ApiRequestOptions = Omit<RequestInit, "body" | "credentials" | "headers"> & {
  body?: unknown;
  /** JSONへ変換せずそのまま送る本文。画像などのバイナリに使う。 */
  rawBody?: BodyInit;
  /** rawBody を送るときの Content-Type。 */
  contentType?: string;
  headers?: HeadersInit;
  timeoutMs?: number;
};

export type ApiClientOptions = {
  baseUrl?: string;
  fetch?: typeof fetch;
  timeoutMs?: number;
};

const DEFAULT_TIMEOUT_MS = 10_000;

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
    const { body, rawBody, contentType, headers: headerInit, timeoutMs: _t, ...init } =
      options;
    const controller = new AbortController();
    const timeoutMs = options.timeoutMs ?? this.timeoutMs;
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
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
