import { describe, expect, it } from "vitest";

import {
  fallbackTextOf,
  initialVoiceState,
  submissionOf,
  voiceReducer,
  VoiceAction,
  VoiceState,
} from "./session";

function run(actions: VoiceAction[], from: VoiceState = initialVoiceState) {
  return actions.reduce(voiceReducer, from);
}

describe("音声入力の状態遷移", () => {
  it("録音を開始して停止すると文字起こし待ちになる", () => {
    expect(run([{ type: "start" }])).toEqual({ status: "listening" });
    expect(run([{ type: "start" }, { type: "stop" }])).toEqual({
      status: "transcribing",
    });
  });

  it("文字起こし結果を編集できる状態で受け取る", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "  庭の草むしりを手伝ってほしい  " },
    ]);

    expect(state).toEqual({
      status: "review",
      draft: "庭の草むしりを手伝ってほしい",
    });
  });

  it("確認前は送信テキストを取り出せない", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "庭の草むしり" },
    ]);

    expect(submissionOf(state)).toBeNull();
  });

  it("文字を修正してから確認すると修正後の内容を送信する", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "庭の草むしり" },
      { type: "edit", text: "庭の草むしりを1時間手伝ってほしい" },
      { type: "confirm" },
    ]);

    expect(state.status).toBe("confirmed");
    expect(submissionOf(state)?.text).toBe("庭の草むしりを1時間手伝ってほしい");
  });

  it("確認した送信テキストへマスクを適用する", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "買い物を頼みたい 090-1234-5678" },
      { type: "confirm" },
    ]);

    expect(submissionOf(state)).toEqual({
      text: "買い物を頼みたい [電話番号]",
      masked: ["phone"],
    });
  });

  it("確認画面から戻って文字を直せる", () => {
    const confirmed = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "庭の草むしり" },
      { type: "confirm" },
    ]);

    const edited = voiceReducer(confirmed, {
      type: "edit",
      text: "庭の草むしりと水やり",
    });

    expect(edited).toEqual({ status: "review", draft: "庭の草むしりと水やり" });
  });

  it("確認済みの内容は何度読み出しても同じ", () => {
    const confirmed = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "買い物を頼みたい" },
      { type: "confirm" },
    ]);

    expect(submissionOf(voiceReducer(confirmed, { type: "confirm" }))).toEqual(
      submissionOf(confirmed),
    );
  });

  it("録音中の取消は結果を残さず最初へ戻す", () => {
    expect(run([{ type: "start" }, { type: "cancel" }])).toEqual({
      status: "idle",
    });
  });

  it("確認前の取消は文字起こし結果を破棄する", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "庭の草むしり" },
      { type: "cancel" },
    ]);

    expect(state).toEqual({ status: "idle" });
    expect(fallbackTextOf(state)).toBe("");
  });

  it("確認画面から録音し直せる", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "庭の草むしり" },
      { type: "start" },
    ]);

    expect(state).toEqual({ status: "listening" });
  });

  it("マイクの権限拒否を失敗として扱う", () => {
    const state = run([
      { type: "start" },
      { type: "fail", reason: "permission-denied" },
    ]);

    expect(state).toEqual({
      status: "error",
      reason: "permission-denied",
      draft: "",
    });
  });

  it.each([
    "recording-failed",
    "transcription-failed",
    "unsupported",
  ] as const)("%s を失敗として案内する", (reason) => {
    const state = run([{ type: "start" }, { type: "fail", reason }]);

    expect(state.status).toBe("error");
    expect(state.status === "error" && state.reason).toBe(reason);
  });

  it("聞き取れなかった録音を失敗として扱う", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "   " },
    ]);

    expect(state).toEqual({
      status: "error",
      reason: "empty-transcript",
      draft: "",
    });
  });

  it("空白だけへ修正した内容は送信しない", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "庭の草むしり" },
      { type: "edit", text: "   " },
      { type: "confirm" },
    ]);

    expect(state.status).toBe("error");
    expect(submissionOf(state)).toBeNull();
  });

  it("失敗しても書きかけの文字を手入力へ引き継ぐ", () => {
    const state = run([
      { type: "start" },
      { type: "stop" },
      { type: "transcribed", text: "庭の草むしり" },
      { type: "fail", reason: "transcription-failed" },
    ]);

    expect(fallbackTextOf(state)).toBe("庭の草むしり");
  });

  it("失敗した後に録音をやり直せる", () => {
    const state = run([
      { type: "start" },
      { type: "fail", reason: "recording-failed" },
      { type: "start" },
    ]);

    expect(state).toEqual({ status: "listening" });
  });

  it("非対応ブラウザでは録音を始めさせない", () => {
    const state = run([
      { type: "start" },
      { type: "fail", reason: "unsupported" },
      { type: "start" },
    ]);

    expect(state.status).toBe("error");
  });
});
