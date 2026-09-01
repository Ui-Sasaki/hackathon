# 画像アップロード

要件定義書 12「ファイル形式、容量、拡張子、MIMEタイプを検証する」
「アップロード画像のメタデータを削除する」、11.3、13.1 と Issue #83 に対応する。

実装は `app/services/images.py`、`app/repositories/uploads.py`、`app/cruds/main.py`。
テストは `tests/test_uploads.py`。

## 1. 流れ

画像は3段階で扱う。端末のローカルURIをプロフィールへ送らせないための分割である。

```
POST /uploads            → uploadId と期限付きの uploadUrl を受け取る
PUT  {uploadUrl}         → 本文を送る。ここで検証とメタデータ除去を行う
PUT  /profile/image      → uploadId を渡して確定する
```

`uploadId` はストレージ内部キーではない。ストレージ内部キー（`private/...`）は
サーバー内部にだけ存在し、どのレスポンスにも現れない。

## 2. エンドポイント

| メソッド | パス | 用途 |
|---|---|---|
| `POST` | `/uploads` | 申告を検証し、期限付きのアップロード先を発行する |
| `PUT` | `/uploads/{upload_id}/content` | 本文を受け取り、検証とメタデータ除去を行う |
| `PUT` | `/profile/image` | アップロードをプロフィール画像として確定する |
| `DELETE` | `/profile/image` | プロフィール画像を削除する |
| `GET` | `/profile/images/{image_token}` | 画像を配信する |

`GET /profile` は `imageUrl`（未設定なら `null`）だけを返す。
`imageId` とストレージ内部キーは公開レスポンスに含めない。

### 状態と応答

| 状況 | ステータス | `code` |
|---|---|---|
| 未認証 | 401 | `AUTHENTICATION_REQUIRED` |
| 他人のアップロード、存在しないID | 404 | `UPLOAD_NOT_FOUND` |
| 対応外のMIME type、実体と不一致、画像でない | 415 | `UNSUPPORTED_MEDIA_TYPE` / `CONTENT_TYPE_MISMATCH` |
| 拡張子とMIME typeの不一致 | 415 | `EXTENSION_MISMATCH` |
| 10MB超過 | 413 | `IMAGE_TOO_LARGE` |
| 壊れた画像 | 422 | `INVALID_IMAGE` |
| 用途の取り違え | 422 | `UPLOAD_PURPOSE_MISMATCH` |
| 本文の二重送信 | 409 | `UPLOAD_ALREADY_COMPLETED` |
| 確定済みの再確定 | 409 | `UPLOAD_ALREADY_USED` |
| 本文未送信での確定 | 409 | `UPLOAD_CONTENT_MISSING` |
| 期限切れ | 409 | `UPLOAD_EXPIRED` |
| 画像未設定での削除 | 404 | `PROFILE_IMAGE_NOT_FOUND` |

他人のアップロードは 403 ではなく 404 を返す。IDの総当たりで存在の有無を
知られないようにするためである。

## 3. 検証

| 対象 | 方法 |
|---|---|
| MIME type | JPEGとPNGだけを受け付ける |
| 拡張子 | ファイル名の拡張子とMIME typeを突き合わせる |
| サイズ | 申告時と受信時の両方で10MB以下を確認する |
| 画像の実体 | 先頭のシグネチャから形式を判定し、申告と一致しない場合は拒否する |

**申告は入口にすぎない。** 保存するかどうかはバイト列そのものから判定する。
拡張子とMIME typeを偽装したファイルは、実体判定の段階で 415 になる。

WebPとGIFは受け付けない。メタデータ除去を安全に行える形式に限定している。

## 4. メタデータ除去

保存前に必ず除去する。再エンコードはせず、不要な領域だけを落とす。

| 形式 | 除去するもの | 残すもの |
|---|---|---|
| JPEG | APP1〜APP15（EXIF、位置情報、端末情報）、コメント（COM） | SOI、APP0（JFIF）、量子化・ハフマンテーブル、SOS以降の画素データ |
| PNG | `tEXt`、`zTXt`、`iTXt`、`tIME`、`eXIf` などの付随チャンク | `IHDR`、`PLTE`、`IDAT`、`IEND`、`tRNS`、`gAMA`、`cHRM`、`sRGB` |

PNGはチャンク単位で捨てるため、残したチャンクのCRCはそのまま有効である。
JPEGはSOS以降に触れないため、画質は変わらない。

## 5. 参照と削除

- 配信URLは `secrets.token_urlsafe(24)` による推測できない参照子を使う。
  利用者ID、ファイル名、ストレージ内部キーをパスへ出さない。
- 配信には認証を要求し、`Cache-Control: private, no-store` を付ける。
- 用途が `profile_image` でない画像はこの経路では返さない。
  本人確認書類がプロフィール画像の配信経路に現れないようにするためである。
- 画像の差し替えは、新しい画像を確定できてから古い画像を消す。
  途中で失敗しても既存の画像は残る。
- 使われなかったアップロードは15分で期限切れとし、`POST /uploads` のたびに回収する。
  本番では定期処理（要件定義書 4「定期処理」）からも回収する想定である。

## 6. 未確定事項

Storage、Postgres、RLS、削除期限、マルウェア対策は担当者との合意事項である。
`docs/cross-team-coordination.md` の COORD-004 を参照。

現在の実装は `MemoryUploadRepository` だけで、画像はプロセス内に保持する。
`UploadRepository` Protocol を境界にしているため、実装を差し替えても
外へ出す値（`uploadId`、`imageUrl`）は変わらない。

## 7. テスト

```bash
.venv/Scripts/python -m pytest tests/test_uploads.py -q
```

- JPEGとPNGのメタデータが実際に消えること
- 拡張子偽装、MIME type偽装、画像でないファイルを拒否すること
- 401、404、409、413、415、422 の各経路
- 他人のアップロードを使えないこと
- 差し替え失敗時に既存画像が残ること
- 公開レスポンスにストレージ内部キーが現れないこと
