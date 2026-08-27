import { getApiBaseUrl } from "./config";
import { ApiAuthenticationError, ApiNetworkError, ApiTimeoutError } from "./errors";

export type ApiRequestOptions = Omit<RequestInit, "body" | "credentials" | "headers"> & {
  body?: unknown;
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

  delete<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: "DELETE" });
  }

  async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    const controller = new AbortController();
    const timeoutMs = options.timeoutMs ?? this.timeoutMs;
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    if (options.body !== undefined) headers.set("Content-Type", "application/json");

    try {
      const fetcher = this.fetchOverride ?? globalThis.fetch;
      const response = await fetcher(`${this.baseUrl}${path}`, {
        ...options,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        credentials: "include",
        headers,
        signal: controller.signal,
      });
      if (response.status === 401) throw new ApiAuthenticationError();
      if (!response.ok) throw new Error(`API request failed with status ${response.status}`);
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
