# テトテFastAPI 開発ガイド

地域の困りごとと支援者をつなぐAPIである。認証・セッション管理にはSuperTokensを使い、業務データ、AI、本人確認は現在インメモリで模擬している。

## セットアップと起動

リポジトリのルートディレクトリで実行する。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m uvicorn main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`
- ヘルスチェック: `http://localhost:8000/health`

起動前にSuperTokens Coreを用意し、必要に応じて次の環境変数を設定する。

| 環境変数 | 既定値 | 用途 |
|---|---|---|
| `SUPERTOKENS_CONNECTION_URI` | `http://localhost:3567` | SuperTokens Core接続先 |
| `SUPERTOKENS_API_KEY` | 未設定 | Core APIキー |
| `API_DOMAIN` | `http://localhost:8000` | API公開元 |
| `WEBSITE_DOMAIN` | `http://localhost:3000` | CORSで許可するフロントエンド |
| `AUTH_COOKIE_SECURE` | `true` | CookieのSecure属性 |
| `AUTH_COOKIE_SAME_SITE` | `lax` | CookieのSameSite属性 |
| `AUTH_MOCK_ENABLED` | `false` | 開発用の認証モックを有効化 |
| `AUTH_MOCK_USER_ID` | `usr_101` | 認証モックの既定ユーザーID |

登録、ログイン、ログアウト、パスワード再設定はSuperTokensの`/auth/*` APIを
利用する。Cookie認証ではHttpOnly/Secure/SameSite Cookieと`anti-csrf`ヘッダーが
使われる。ローカルHTTP開発時だけ`AUTH_COOKIE_SECURE=false`にする。
ユーザー登録に成功すると、SuperTokensのユーザーIDに対応するアプリ内プロフィールを
依頼者・未確認の初期状態で自動作成する。

### SuperTokensなしで機能を試す

ローカル開発時は、次のように起動するとSuperTokensのセッション検証を認証モックへ
差し替えられる。

```bash
SUPERTOKENS_ENABLED=false AUTH_MOCK_ENABLED=true python -m uvicorn main:app --reload --port 8000
```

既定では`usr_101`（依頼者）として扱われる。別ユーザーの動作を確認する場合は
`X-Mock-User-Id: usr_207`（支援者）のように、モックデータに存在するユーザーIDを
指定する。既定ユーザーは`AUTH_MOCK_USER_ID`でも変更できる。ロール、利用停止状態、
本人確認状態など、アプリ側の認可判定は通常どおり実行される。

`AUTH_MOCK_ENABLED`はリクエストヘッダーを本人情報として信用する開発専用機能である。
共有環境や本番環境では有効にしないこと。

`/requests` と `/api/requests` のように、各APIは `/api` 接頭辞の有無に対応する。

## フォルダ構成

```text
./
├── main.py              # uvicorn用エントリーポイント
├── app/
│   ├── main.py          # ASGIアプリの公開
│   ├── cruds/main.py    # エンドポイントとインメモリCRUD
│   ├── routers/main.py  # システム系ルーター
│   └── schemas/main.py  # Pydantic入力スキーマ
└── tests/main.py        # APIテスト
```

入力項目を変更するときは `schemas/main.py`、APIや状態遷移を変更するときは `cruds/main.py`、ヘルスチェックなどのシステム系APIは `routers/main.py` を編集する。

## 主要エンドポイント

| Method | Path | 説明 |
|---|---|---|
| GET | `/health` | ヘルスチェック |
| POST | `/auth/signup` | ユーザー登録 |
| POST | `/auth/signin` | ログイン |
| POST | `/auth/signout` | ログアウト |
| POST | `/auth/user/password/reset/token` | パスワード再設定メール送信 |
| POST | `/auth/user/password/reset` | パスワード再設定・既存セッション失効 |
| GET / PATCH | `/profile` | プロフィール取得・更新 |
| POST | `/requests/structure` | 依頼文の構造化 |
| GET / POST | `/requests` | 依頼一覧・作成 |
| GET / PATCH / DELETE | `/requests/{id}` | 依頼取得・更新・取消 |
| POST | `/requests/{id}/applications` | 依頼への応募 |
| GET | `/requests/{id}/applications` | 応募者一覧 |
| POST | `/applications/{id}/select` | 応募者選択 |
| POST | `/applications/{id}/withdraw` | 応募取り下げ |
| GET / POST | `/matches/{id}/messages` | チャット取得・送信 |
| POST | `/matches/{id}/complete` | 完了確認 |
| POST | `/matches/{id}/dispute` | マッチングキャンセル |
| POST | `/matches/{id}/reviews` | 評価投稿 |
| POST | `/achievements/generate` | 実績生成 |
| POST | `/verifications` | 本人確認申請 |
| POST | `/reports` | 通報 |
| POST | `/users/{id}/block` | ブロック・解除 |

詳細なリクエスト・レスポンス仕様はSwagger UIを参照する。

### 依頼一覧・検索

`GET /requests` は `category`、`scheduledFrom`、`scheduledTo`、
`maxDistanceKm`、`requiredHelpers`、`verificationStatus` で公開中の依頼を検索する。
`latitude` と `longitude` は必ず組で指定し、省略時は認証ユーザーの登録地域
（`areaCode`）を検索起点として利用する。標準取得件数は20件、`limit` の上限は100件で、
続きはレスポンスの `nextCursor` を `cursor` に指定して取得する。期限切れや募集終了した
依頼は含まれず、レスポンスには番地および正確な緯度・経度を含めない。

## エラーレスポンスとトレースID

400、401、403、404、409、422、500 のエラーは、次の共通形式で返す。

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "入力内容を確認してください",
    "details": {},
    "requestId": "trace_0123abcd"
  }
}
```

`requestId` はレスポンスの `X-Request-ID` ヘッダーにも設定され、サーバーログの
`requestId` と照合できる。検証エラーには入力値を含めず、500 エラーでは内部例外を
公開しない。

## 開発とテスト

```bash
python -m pytest -q
```

モックデータを初期状態へ戻す場合は次を実行する。

```bash
curl -X POST http://localhost:8000/_mock/reset
```

データはプロセス内だけに保存され、サーバーを再起動すると初期化される。本番環境では認証、認可、永続DB、CSRF対策、レート制限を本実装へ置き換えること。
