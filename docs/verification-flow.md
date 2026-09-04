# 本人確認申請のAPI接続

Issue #86、TODO 29 に対応する。要件定義書 11.3、12 を前提とする。

バックエンドは `app/cruds/main.py` の `POST /verifications`、
フロントエンドは `tetote/src/verification/` と `tetote/src/shared/VerificationScreen.tsx`。
画像アップロードの詳細は `docs/image-upload.md` を参照。

## 1. 契約の変更

以前の `POST /verifications` は、学生証方式で `storageObjectKey`
（非公開ストレージのキー）をクライアントから受け取っていた。
クライアントがストレージ内部キーを知る前提だったため、`uploadId` を受け取る形へ変えた。

| 変更前 | 変更後 |
|---|---|
| `{"method": "student_card", "storageObjectKey": "private/..."}` | `{"method": "student_card", "uploadId": "<uuid>"}` |

`uploadId` は `POST /uploads` が発行する識別子で、ストレージ内部キーではない。
サーバーは受け取った `uploadId` の所有者・用途・状態を確認してから画像を確定し、
内部の画像参照はレスポンスにも含めない。

## 2. 流れ

```
（学生証方式のみ）
POST /uploads                    purpose: verification_document
PUT  /uploads/{id}/content       画像本文。検証とメタデータ除去はサーバー側

POST /verifications              { method, uploadId }
GET  /profile                    verificationStatus が pending になる
```

大学メール方式では画像を送らないため、`uploadId` は送らない。

## 3. サーバー側の確認事項

| 確認 | 応答 |
|---|---|
| 学生証方式で `uploadId` がない | 422 `UPLOAD_REQUIRED` |
| 審査中の申請が既にある | 409 `VERIFICATION_ALREADY_PENDING` |
| 他人のアップロード、存在しないID | 404 `UPLOAD_NOT_FOUND` |
| 用途が `verification_document` でない | 422 `UPLOAD_PURPOSE_MISMATCH` |
| 本文未送信 | 409 `UPLOAD_CONTENT_MISSING` |
| 確定済みの再利用 | 409 `UPLOAD_ALREADY_USED` |
| 期限切れ | 409 `UPLOAD_EXPIRED` |

重複確認は画像の確定より**先**に行う。重複で弾かれた申請がアップロードを
消費してしまうと、利用者が画像を選び直す必要が出るためである。

本人確認書類は用途が `verification_document` のため、プロフィール画像の配信経路
（`GET /profile/images/{image_token}`）には現れない。

## 4. 画面の状態

`tetote/src/verification/state.ts` に純粋な関数として置き、画面から切り離してテストする。

| 状態 | 表示 |
|---|---|
| `idle` | 方式の選択と申請ボタン |
| `uploading` | 「写真を送っています...」 |
| `submitting` | 「申請しています...」 |
| `submitted` | 「申請を受け付けました」 |
| `error` | 理由と「もう一度試す」 |

### 送信できる条件（`canSubmit`）

- 送信中と申請済みでは押せない
- `verificationStatus` が `pending` または `approved` なら押せない（**重複申請の防止**）
- 学生証方式は画像を選ぶまで押せない
- `rejected` と `expired` からは申請し直せる

`emailVerified` と `verificationStatus` は別々に保持し、画面でも別の行として表示する。
申請はメール確認状態を変えない。

### 失敗の表示（`describeFailure`）

401、403、409、413、415、422、通信失敗をすべて画面の文言へ変換する。
サーバーのメッセージはそのまま表示しない。既知の理由コードは画面側の文言に寄せ、
未知のコードは汎用の文言にする。内部情報が画面へ漏れないようにするためである。

## 5. 秘密情報の扱い

- 画面が保持するのは `uploadId` だけで、ストレージ内部キー、署名、Service Role Key は持たない。
- 端末ローカルURIはアップロード直前に実体へ変換し、APIへは渡さない。
- 失敗時にログへ出すのは理由コードと画面向け文言だけで、画像の中身とファイル名は出さない。

## 6. 未確定事項

Storage、Postgres、RLS、削除期限は `docs/cross-team-coordination.md` の COORD-004 を参照。
現在の審査実装は Memory のみである。本人確認担当者または管理者（MFA必須）は、
`GET /verification-reviews`、書類閲覧URLの発行、承認・否認、審査済み書類の削除を行える。
閲覧URLは5分間かつ発行先の担当者だけに有効で、発行・閲覧・判断・削除を監査する。
Postgres、private Storage、期限到来時の定期削除は
`docs/cross-team-coordination.md` の COORD-004 を参照する。

### 審査API

| API | 用途 |
|---|---|
| `GET /verification-reviews` | 審査待ち一覧（画像・内部キーは含まない） |
| `POST /verification-reviews/{id}/document-access` | 5分間の閲覧URLを発行 |
| `GET /verification-documents/{token}` | 発行先担当者が書類を閲覧。`no-store` |
| `POST /verification-reviews/{id}/decision` | `approved` または `rejected` へ遷移 |
| `DELETE /verification-reviews/{id}/document` | 審査済み書類を削除 |

## 7. テスト

```bash
.venv/Scripts/python -m pytest tests/test_verifications.py -q
cd tetote && npm test
```

| ファイル | 対象 |
|---|---|
| `tests/test_verifications.py` | 申請の受理、重複防止、他人のアップロード、用途違い、401 |
| `tetote/src/verification/client.test.ts` | 送信内容、Cookie、失敗時に本文を送らないこと |
| `tetote/src/verification/state.test.ts` | 送信中・失敗・再試行・申請済み、重複防止、エラー変換 |
