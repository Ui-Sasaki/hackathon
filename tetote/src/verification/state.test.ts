import { describe, expect, it } from "vitest";

import { ApiAuthenticationError, ApiError, ApiNetworkError, ApiTimeoutError } from "../api/errors";
import {
  canSubmit,
  describeFailure,
  initialSubmissionState,
  isBusy,
  submissionReducer,
  SubmissionState,
} from "./state";

function run(actions: Parameters<typeof submissionReducer>[1][]): SubmissionState {
  return actions.reduce(submissionReducer, initialSubmissionState);
}

describe("本人確認申請の状態遷移", () => {
  it("送信を開始すると画像送信中になる", () => {
    expect(run([{ type: "upload_started" }])).toEqual({ status: "uploading" });
  });

  it("画像を送り終えると申請送信中になる", () => {
    expect(run([{ type: "upload_started" }, { type: "upload_finished" }])).toEqual({
      status: "submitting",
    });
  });

  it("送信中の二重発火を無視する", () => {
    const state = run([{ type: "upload_started" }, { type: "upload_started" }]);
    expect(state).toEqual({ status: "uploading" });
  });

  it("成功すると申請済みになる", () => {
    const state = run([
      { type: "upload_started" },
      { type: "upload_finished" },
      { type: "succeeded" },
    ]);
    expect(state).toEqual({ status: "submitted" });
  });

  it("失敗すると理由を保持する", () => {
    const state = run([
      { type: "upload_started" },
      { type: "failed", code: "IMAGE_TOO_LARGE", message: "画像は10MBまでにしてください" },
    ]);
    expect(state).toEqual({
      status: "error",
      code: "IMAGE_TOO_LARGE",
      message: "画像は10MBまでにしてください",
    });
  });

  it("失敗からやり直せる", () => {
    const state = run([
      { type: "upload_started" },
      { type: "failed", code: "NETWORK_ERROR", message: "通信できませんでした" },
      { type: "retry" },
    ]);
    expect(state).toEqual({ status: "idle" });
  });

  it("申請済みからは戻さない", () => {
    const state = run([
      { type: "upload_started" },
      { type: "upload_finished" },
      { type: "succeeded" },
      { type: "retry" },
    ]);
    expect(state).toEqual({ status: "submitted" });
  });

  it.each([
    [{ status: "uploading" } as SubmissionState, true],
    [{ status: "submitting" } as SubmissionState, true],
    [{ status: "idle" } as SubmissionState, false],
    [{ status: "submitted" } as SubmissionState, false],
  ])("送信中かどうかを判定する", (state, expected) => {
    expect(isBusy(state)).toBe(expected);
  });
});

describe("送信できるかの判定", () => {
  const base = {
    state: initialSubmissionState,
    verificationStatus: "unverified" as const,
    method: "university_email" as const,
    hasDocument: false,
  };

  it("未確認なら大学メール方式で送信できる", () => {
    expect(canSubmit(base)).toBe(true);
  });

  it("審査中は重複申請させない", () => {
    expect(canSubmit({ ...base, verificationStatus: "pending" })).toBe(false);
  });

  it("承認済みは再申請させない", () => {
    expect(canSubmit({ ...base, verificationStatus: "approved" })).toBe(false);
  });

  it("却下されたら申請し直せる", () => {
    expect(canSubmit({ ...base, verificationStatus: "rejected" })).toBe(true);
  });

  it("学生証方式は画像を選ぶまで送信できない", () => {
    expect(canSubmit({ ...base, method: "student_card" })).toBe(false);
    expect(canSubmit({ ...base, method: "student_card", hasDocument: true })).toBe(true);
  });

  it("送信中は押し直せない", () => {
    expect(canSubmit({ ...base, state: { status: "uploading" } })).toBe(false);
    expect(canSubmit({ ...base, state: { status: "submitting" } })).toBe(false);
  });

  it("申請済みからは送れない", () => {
    expect(canSubmit({ ...base, state: { status: "submitted" } })).toBe(false);
  });
});

describe("失敗理由の変換", () => {
  it.each([
    [401, "AUTHENTICATION_REQUIRED"],
    [403, "ROLE_FORBIDDEN"],
    [422, "VALIDATION_ERROR"],
  ])("ステータス %i を画面向けの文言へ変える", (status, code) => {
    const described = describeFailure(
      status === 401
        ? new ApiAuthenticationError({ code })
        : new ApiError({ status, code, message: "サーバー側の文言" }),
    );

    expect(described.code).toBe(code);
    expect(described.message).not.toBe("サーバー側の文言");
    expect(described.message.length).toBeGreaterThan(0);
  });

  it.each([
    ["VERIFICATION_ALREADY_PENDING", "すでに審査中の申請があります。結果をお待ちください"],
    ["IMAGE_TOO_LARGE", "画像は10MBまでにしてください"],
    ["UNSUPPORTED_MEDIA_TYPE", "JPEGまたはPNGの画像を選んでください"],
    ["UPLOAD_EXPIRED", "時間が経ちすぎました。画像を選び直してください"],
  ])("コード %s に対応する案内を返す", (code, message) => {
    const described = describeFailure(
      new ApiError({ status: 409, code, message: "サーバー側の文言" }),
    );
    expect(described.message).toBe(message);
  });

  it("通信失敗を再試行できる案内へ変える", () => {
    const described = describeFailure(new ApiNetworkError());
    expect(described.code).toBe("NETWORK_ERROR");
    expect(described.message).toContain("通信できませんでした");
  });

  it("タイムアウトも通信失敗として扱う", () => {
    expect(describeFailure(new ApiTimeoutError()).code).toBe("NETWORK_ERROR");
  });

  it("想定外の例外でも文言を返す", () => {
    const described = describeFailure(new Error("boom"));
    expect(described.code).toBe("UNKNOWN_ERROR");
    expect(described.message).not.toContain("boom");
  });

  it("知らないコードはサーバーの文言をそのまま出さない", () => {
    const described = describeFailure(
      new ApiError({ status: 500, code: "SOME_INTERNAL_CODE", message: "stack trace" }),
    );
    expect(described.message).not.toContain("stack trace");
  });
});
