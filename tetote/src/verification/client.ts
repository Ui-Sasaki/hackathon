/**
 * 本人確認申請と、そのための画像アップロードをAPIへ繋ぐ層。
 *
 * 画面が扱うのは `uploadId` だけで、ストレージ内部キーや署名は一切保持しない。
 * 画像の中身とファイル名はログへ出さない。
 */

import { ApiClient, apiClient } from "../api/client";

export type VerificationMethod = "university_email" | "student_card";

export type VerificationStatus =
  | "unverified"
  | "pending"
  | "approved"
  | "rejected"
  | "expired";

export type DocumentImageType = "image/jpeg" | "image/png";

export type DocumentImage = {
  /** 送信する画像の実体。 */
  data: Blob | ArrayBuffer;
  contentType: DocumentImageType;
  byteSize: number;
  /** 拡張子の突き合わせだけに使う。サーバーは保存しない。 */
  fileName?: string;
};

export type UploadSession = {
  uploadId: string;
  uploadUrl: string;
  expiresAt: string;
  maxBytes: number;
};

export type VerificationApplication = {
  id: string;
  userId: string;
  method: VerificationMethod;
  status: VerificationStatus;
  createdAt: string;
};

/**
 * 学生証画像をアップロードし、申請へ渡せる識別子だけを返す。
 */
export async function uploadVerificationDocument(
  image: DocumentImage,
  client: ApiClient = apiClient,
): Promise<string> {
  const session = await client.post<UploadSession>("/uploads", {
    purpose: "verification_document",
    contentType: image.contentType,
    byteSize: image.byteSize,
    fileName: image.fileName,
  });

  await client.request(session.uploadUrl, {
    method: "PUT",
    rawBody: image.data,
    contentType: image.contentType,
  });

  return session.uploadId;
}

/**
 * 本人確認を申請する。送るのは方式と、アップロードの識別子だけ。
 */
export async function submitVerification(
  input: { method: VerificationMethod; uploadId?: string },
  client: ApiClient = apiClient,
): Promise<VerificationApplication> {
  return client.post<VerificationApplication>("/verifications", {
    method: input.method,
    uploadId: input.method === "student_card" ? input.uploadId : undefined,
  });
}
