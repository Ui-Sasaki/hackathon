import { afterEach, describe, expect, it, vi } from "vitest";

import { apiConfigurationProblem, getApiBaseUrl, isApiBaseUrlConfigured, isLocalUrl } from "./config";

const ORIGINAL = process.env.EXPO_PUBLIC_API_URL;

afterEach(() => {
  if (ORIGINAL === undefined) {
    delete process.env.EXPO_PUBLIC_API_URL;
  } else {
    process.env.EXPO_PUBLIC_API_URL = ORIGINAL;
  }
  vi.unstubAllGlobals();
});

function withApiUrl(value: string | undefined): void {
  if (value === undefined) {
    delete process.env.EXPO_PUBLIC_API_URL;
  } else {
    process.env.EXPO_PUBLIC_API_URL = value;
  }
}

describe("APIの接続先", () => {
  it("設定された値の末尾のスラッシュを落とす", () => {
    withApiUrl("https://api.example.com/");
    expect(getApiBaseUrl()).toBe("https://api.example.com");
  });

  it("未設定なら手元のPCへ落ちる", () => {
    withApiUrl(undefined);
    expect(getApiBaseUrl()).toBe("http://localhost:8000");
    expect(isApiBaseUrlConfigured()).toBe(false);
  });

  it.each([
    ["http://localhost:8000", true],
    ["http://127.0.0.1:8000", true],
    ["https://api.example.com", false],
    ["not a url", false],
  ])("%s がローカル向きかを判定する", (url, expected) => {
    expect(isLocalUrl(url)).toBe(expected);
  });
});

describe("公開後の設定漏れの検出", () => {
  it("公開URLから開かれているのに手元のPCを指していたら知らせる", () => {
    withApiUrl(undefined);
    const problem = apiConfigurationProblem("tetote.vercel.app");

    expect(problem).toContain("EXPO_PUBLIC_API_URL");
  });

  it("手元で開発している間は知らせない", () => {
    withApiUrl(undefined);
    expect(apiConfigurationProblem("localhost")).toBeNull();
    expect(apiConfigurationProblem("127.0.0.1")).toBeNull();
  });

  it("接続先が設定されていれば知らせない", () => {
    withApiUrl("https://api.example.com");
    expect(apiConfigurationProblem("tetote.vercel.app")).toBeNull();
  });

  it("ブラウザ以外では判定しない", () => {
    withApiUrl(undefined);
    expect(apiConfigurationProblem(null)).toBeNull();
  });
});
