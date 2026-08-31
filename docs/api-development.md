# フロントエンド向けAPI開発ガイド

APIを `.venv/bin/python -m uvicorn main:app --reload --port 8000` で起動し、
Swagger UI（`http://localhost:8000/docs`）をAPI契約として参照する。固定版は
`docs/openapi.json` で、変更後は次のコマンドによりFastAPIアプリから再生成する。

```bash
.venv/bin/python scripts/export_openapi.py
```

## 認証

業務APIはすべてSuperTokensのHttpOnly Cookieセッションを要求する。登録、ログイン、
ログアウト、パスワード再設定はSuperTokensが提供する `/auth/*` を使う。更新系では
SDKが設定する `anti-csrf` ヘッダーも必要である。`userId`、`requesterId`、
`reporterId`、ロール、送信日時をクライアントから送っても本人情報として信用されない。

単体テストではSuperTokens依存関係を差し替える。開発用の認証ヘッダーは実装しておらず、
本番でも利用できない。初期モック利用者は次のとおり（パスワードは用意されていない）。

| ID | 表示名 | 用途 |
|---|---|---|
| `usr_101` | 山田 花子 | 初期依頼者・承認済み会員 |
| `usr_207` | 田中 悠 | 初期応募者・承認済み会員 |
| `usr_208` | 佐藤 海 | 初期応募者・未確認会員 |

`MOCK_RESET_ENABLED=true` の非本番環境では、認証済みセッションから
`POST /_mock/reset` を呼ぶと全モックデータを初期化できる。既定では無効で、
本番用APIではない。

## 共通規約

- 日時はISO 8601文字列。サーバー生成日時はUTCの `Z`、入力日時はタイムゾーン必須。
- エラーは `{"error":{"code":"...","message":"...","details":{},"requestId":"trace_..."}}`。
  `requestId` は `X-Request-ID` と一致する。
- 依頼一覧の既定件数は20、最大100。公開中かつブロック関係にない依頼だけを返す。
  Repositoryでは `createdAt`、IDの降順で取得後、現在地または登録地域への近さを反映する。
- 一覧の `nextCursor` が `null` なら次ページはない。現行の依頼・メッセージ一覧は
  カーソル入力未実装のため常に `null`。
- `/api` 接頭辞あり・なしの両方を実行時に受け付ける。OpenAPIでは正規パスとして
  接頭辞なしを掲載する。

## 実装状況

### 利用者設定

`GET /settings` と `PATCH /settings` は、認証済み本人の `notificationsEnabled`、
`locationEnabled`、`fontSize`（`small`、`medium`、`large`）を取得・部分更新する。
未指定項目は維持される。`locationEnabled: false` の間、画面はブラウザ位置情報の
取得を開始しない。`notificationsEnabled` はアプリ内の通知希望であり、ブラウザや
OSの通知権限自体を付与・解除するものではない。

現在はMemory Repositoryを使用する。Postgres実装、migration、RLSはSupabase担当との
合意後に追加する。`tetote/src/shared/SettingsScreen.tsx` は初回表示時にGETを行い、
各操作をPATCHした成功レスポンスで表示状態を確定できる。

### 依頼カードの非表示

`POST /requests/{request_id}/dismiss` は認証済み本人の一覧から依頼を非表示にし、
`DELETE /requests/{request_id}/dismiss` は非表示を解除する。どちらも冪等で成功時は
204を返す。`GET /requests` は本人が非表示にした依頼だけを除外し、他利用者の一覧へ
影響しない。存在しない依頼、公開中でない依頼、ブロック関係など存在を開示できない
依頼への操作は404となる。

現在はMemory Repositoryを使用する。Postgres実装、migration、RLSはSupabase担当との
合意後に追加する。`tetote/src/context/RequestsContext.tsx` はスキップ操作の成功後に
対象を画面状態から除外し、再取得後はAPI一覧を正本として表示できる。

依頼CRUDはMemory/Postgres Repositoryに対応する。プロフィール、位置解決、応募、
マッチ、チャット、完了、レビュー、AI実績、本人確認、通報、ブロックのAPI経路と
状態・認可検査は実装済みだが、依頼以外の保存、AI生成、本人確認審査は開発用
インメモリ／モックである。SuperTokensの `/auth/*` はSDK提供であり、FastAPI生成の
OpenAPIには個別操作として現れない。管理画面、Realtime、実AI、本人確認審査、
証明画像アップロード、カーソルによる次ページ取得は未実装である。
