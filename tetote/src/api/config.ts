const DEFAULT_API_URL = "http://localhost:8000";

const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

export function getApiBaseUrl(): string {
  return (process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_API_URL).replace(/\/+$/, "");
}

/** `EXPO_PUBLIC_API_URL` が指定されているか。未指定なら localhost へ落ちている。 */
export function isApiBaseUrlConfigured(): boolean {
  return Boolean(process.env.EXPO_PUBLIC_API_URL);
}

export function isLocalUrl(url: string): boolean {
  try {
    return LOCAL_HOSTNAMES.has(new URL(url).hostname);
  } catch {
    return false;
  }
}

/**
 * 公開された場所から開かれているのに、APIの接続先が手元のPCを指していないか。
 *
 * `EXPO_PUBLIC_API_URL` はビルド時にコードへ埋め込まれる。未設定のまま公開すると
 * 閲覧者自身のPCへ接続しようとして必ず失敗するが、ビルドは成功してしまうため、
 * 通信エラーとは区別して伝えられるようにする。
 */
export function apiConfigurationProblem(
  pageHostname: string | null = typeof window === "undefined"
    ? null
    : window.location.hostname,
): string | null {
  if (!isLocalUrl(getApiBaseUrl())) {
    return null;
  }
  if (pageHostname === null || LOCAL_HOSTNAMES.has(pageHostname)) {
    return null;
  }
  return "APIの接続先が設定されていません。EXPO_PUBLIC_API_URL を設定して再ビルドしてください";
}
