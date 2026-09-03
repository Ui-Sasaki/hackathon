import { afterEach, describe, expect, it, vi } from "vitest";

import { toErrorReason, webSpeechAdapter } from "./recognition";
import { VoiceErrorReason } from "./session";

class FakeRecognition {
  lang = "";
  interimResults = false;
  continuous = false;
  started = false;
  aborted = false;
  onresult: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onend: (() => void) | null = null;
  static failOnStart = false;

  start() {
    if (FakeRecognition.failOnStart) {
      throw new Error("start failed");
    }

    this.started = true;
  }

  stop() {
    this.onend?.();
  }

  abort() {
    this.aborted = true;
    this.onend?.();
  }

  emit(text: string) {
    this.onresult?.({ results: [[{ transcript: text }]], length: 1 });
  }
}

function installRecognition(): FakeRecognition[] {
  const created: FakeRecognition[] = [];

  vi.stubGlobal("window", {
    SpeechRecognition: class extends FakeRecognition {
      constructor() {
        super();
        created.push(this);
      }
    },
  });

  return created;
}

function handlers() {
  return {
    onTranscript: vi.fn(),
    onError: vi.fn<(reason: VoiceErrorReason) => void>(),
  };
}

afterEach(() => {
  FakeRecognition.failOnStart = false;
  vi.unstubAllGlobals();
});

describe("ブラウザの音声認識アダプタ", () => {
  it("認識APIがないブラウザを非対応として案内する", () => {
    vi.stubGlobal("window", {});
    const events = handlers();

    expect(webSpeechAdapter.isSupported()).toBe(false);

    webSpeechAdapter.start(events);

    expect(events.onError).toHaveBeenCalledWith("unsupported");
  });

  it("停止したときだけ文字起こし結果を渡す", () => {
    const created = installRecognition();
    const events = handlers();

    const controller = webSpeechAdapter.start(events);
    created[0].emit("庭の草むしりを手伝ってほしい");

    expect(events.onTranscript).not.toHaveBeenCalled();

    controller.stop();

    expect(events.onTranscript).toHaveBeenCalledWith(
      "庭の草むしりを手伝ってほしい",
    );
  });

  it("取消した録音は結果を渡さない", () => {
    const created = installRecognition();
    const events = handlers();

    const controller = webSpeechAdapter.start(events);
    created[0].emit("取り消す内容");
    controller.abort();

    expect(created[0].aborted).toBe(true);
    expect(events.onTranscript).not.toHaveBeenCalled();
    expect(events.onError).not.toHaveBeenCalled();
  });

  it("マイクの権限拒否を権限エラーとして渡す", () => {
    const created = installRecognition();
    const events = handlers();

    webSpeechAdapter.start(events);
    created[0].onerror?.({ error: "not-allowed" });

    expect(events.onError).toHaveBeenCalledWith("permission-denied");
  });

  it("取消由来の aborted は失敗として扱わない", () => {
    const created = installRecognition();
    const events = handlers();

    webSpeechAdapter.start(events);
    created[0].onerror?.({ error: "aborted" });

    expect(events.onError).not.toHaveBeenCalled();
  });

  it("録音の開始に失敗したら録音エラーとして案内する", () => {
    installRecognition();
    FakeRecognition.failOnStart = true;
    const events = handlers();

    webSpeechAdapter.start(events);

    expect(events.onError).toHaveBeenCalledWith("recording-failed");
  });

  it("認識は日本語で1回分だけ受け付ける設定にする", () => {
    const created = installRecognition();

    webSpeechAdapter.start(handlers());

    expect(created[0].lang).toBe("ja-JP");
    expect(created[0].interimResults).toBe(false);
    expect(created[0].continuous).toBe(false);
  });

  it.each([
    ["not-allowed", "permission-denied"],
    ["service-not-allowed", "permission-denied"],
    ["audio-capture", "recording-failed"],
    ["no-speech", "empty-transcript"],
    ["network", "transcription-failed"],
    ["unknown-code", "transcription-failed"],
  ] as const)("エラーコード %s を %s へ寄せる", (code, reason) => {
    expect(toErrorReason(code)).toBe(reason);
  });
});
