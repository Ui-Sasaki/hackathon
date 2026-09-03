#!/usr/bin/env node
/**
 * 公開ビルドの直前に、APIの接続先が設定されているかを確認する。
 *
 * EXPO_PUBLIC_API_URL はビルド時にコードへ埋め込まれる。未設定のまま公開すると
 * フロントエンドは http://localhost:8000、つまり閲覧者自身のPCへ接続しようとして
 * 必ず失敗する。それでもビルドは成功してしまうため、ここで止める。
 *
 * ローカルで公開ビルドを試すときは ALLOW_LOCALHOST_API=1 を付ける。
 */

const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

function fail(message) {
  console.error(`\n[check-api-url] ${message}\n`);
  process.exit(1);
}

const configured = process.env.EXPO_PUBLIC_API_URL;

if (process.env.ALLOW_LOCALHOST_API === "1") {
  console.log("[check-api-url] ALLOW_LOCALHOST_API=1 のため確認を省略しました");
  process.exit(0);
}

if (!configured) {
  fail(
    "EXPO_PUBLIC_API_URL が設定されていません。\n" +
      "このままビルドすると、公開後にフロントエンドが閲覧者自身のPC (http://localhost:8000) へ\n" +
      "接続しようとして、新規登録とログインが必ず失敗します。\n" +
      "ホスティングの環境変数へ本番APIのURLを設定してから、もう一度ビルドしてください。",
  );
}

let url;
try {
  url = new URL(configured);
} catch {
  fail(`EXPO_PUBLIC_API_URL がURLとして解釈できません: ${configured}`);
}

if (LOCAL_HOSTNAMES.has(url.hostname)) {
  fail(
    `EXPO_PUBLIC_API_URL が手元のPCを指しています: ${configured}\n` +
      "公開ビルドでは到達できません。本番APIのURLを設定してください。",
  );
}

if (url.protocol !== "https:") {
  fail(
    `EXPO_PUBLIC_API_URL が https ではありません: ${configured}\n` +
      "HTTPSページからHTTPのAPIへは接続できず、Cookieも送信されません。",
  );
}

console.log(`[check-api-url] 接続先を確認しました: ${url.origin}`);
