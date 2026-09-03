import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../api/client";
import { ApiError } from "../api/errors";
import { submitVerification, uploadVerificationDocument } from "./client";

const UPLOAD_SESSION = {
  uploadId: "upload-1",
  uploadUrl: "/uploads/upload-1/content",
  expiresAt: "2026-09-01T00:15:00Z",
  maxBytes: 10 * 1024 * 1024,
};

const STORED_CONTENT = {
  uploadId: "upload-1",
  status: "stored",
  contentType: "image/png",
  byteSize: 3,
};

const APPLICATION = {
  id: "verification-1",
  userId: "usr_101",
  method: "student_card",
  status: "pending",
  createdAt: "2026-09-01T00:00:00Z",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, code: string): Response {
  return new Response(
    JSON.stringify({
      error: { code, message: "サーバー側の文言", details: {}, requestId: "trace_1" },
    }),
    { status, headers: { "Content-Type": "application/json" } },
  );
}

function clientWith(fetchMock: ReturnType<typeof vi.fn>): ApiClient {
  return new ApiClient({ baseUrl: "http://api.test", fetch: fetchMock as never });
}

const image = {
  data: new Uint8Array([1, 2, 3]).buffer,
  contentType: "image/png" as const,
  byteSize: 3,
  fileName: "card.png",
};

describe("本人確認画像のアップロード", () => {
  it("開始してから本文を送り、識別子だけを返す", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(UPLOAD_SESSION))
      .mockResolvedValueOnce(jsonResponse(STORED_CONTENT));

    const uploadId = await uploadVerificationDocument(image, clientWith(fetchMock));

    expect(uploadId).toBe("upload-1");
    const [startUrl, startInit] = fetchMock.mock.calls[0];
    expect(startUrl).toBe("http://api.test/uploads");
    expect(JSON.parse(startInit.body)).toEqual({
      purpose: "verification_document",
      contentType: "image/png",
      byteSize: 3,
      fileName: "card.png",
    });
  });

  it("本文はJSONへ変換せず、宣言した形式で送る", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(UPLOAD_SESSION))
      .mockResolvedValueOnce(jsonResponse(STORED_CONTENT));

    await uploadVerificationDocument(image, clientWith(fetchMock));

    const [contentUrl, contentInit] = fetchMock.mock.calls[1];
    expect(contentUrl).toBe("http://api.test/uploads/upload-1/content");
    expect(contentInit.method).toBe("PUT");
    expect(contentInit.body).toBe(image.data);
    expect(new Headers(contentInit.headers).get("Content-Type")).toBe("image/png");
  });

  it("セッションCookieを送る", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(UPLOAD_SESSION))
      .mockResolvedValueOnce(jsonResponse(STORED_CONTENT));

    await uploadVerificationDocument(image, clientWith(fetchMock));

    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
    expect(fetchMock.mock.calls[1][1].credentials).toBe("include");
  });

  it("開始に失敗したら本文を送らない", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(errorResponse(413, "IMAGE_TOO_LARGE"));

    await expect(
      uploadVerificationDocument(image, clientWith(fetchMock)),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("本人確認の申請", () => {
  it("方式とアップロード識別子だけを送る", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(APPLICATION, 201));

    const result = await submitVerification(
      { method: "student_card", uploadId: "upload-1" },
      clientWith(fetchMock),
    );

    expect(result.status).toBe("pending");
    const sent = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(sent).toEqual({ method: "student_card", uploadId: "upload-1" });
    // ストレージ内部キーや秘密情報を混ぜない。
    expect(Object.keys(sent)).toEqual(["method", "uploadId"]);
  });

  it("大学メール方式では画像の識別子を送らない", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(APPLICATION, 201));

    await submitVerification(
      { method: "university_email", uploadId: "upload-1" },
      clientWith(fetchMock),
    );

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      method: "university_email",
    });
  });

  it("審査中の重複申請をエラーとして返す", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(errorResponse(409, "VERIFICATION_ALREADY_PENDING"));

    await expect(
      submitVerification({ method: "university_email" }, clientWith(fetchMock)),
    ).rejects.toMatchObject({ status: 409, code: "VERIFICATION_ALREADY_PENDING" });
  });
});
