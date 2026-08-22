# テトテFastAPI 開発ガイド

地域の困りごとと支援者をつなぐAPIである。認証・セッション管理にはSuperTokensを使い、依頼（`requests`）はPostgres（Supabase）へ永続化されている（#4）。応募・マッチング・チャット等その他の業務データ、AI、本人確認は現在インメモリで模擬している。

依頼周りのエンドポイントを動かすには `DATABASE_URL` が要る。`.env.example` を `.env` にコピーし、値を埋めること。`supabase/tests/run.sh` でローカルのPostgresを用意できる。

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
| `MOCK_RESET_ENABLED` | `false` | `POST /_mock/reset` を利用可能にする。開発・テスト環境でのみ有効にする |

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
│   ├── db.py            # Postgres接続・actor scoped transaction（#4）
│   ├── cruds/main.py    # エンドポイントとCRUD（requestsはPostgres、他はインメモリ）
│   ├── routers/main.py  # システム系ルーター
│   └── schemas/main.py  # Pydantic入力スキーマ
├── supabase/
│   ├── migrations/      # スキーマ・RLS・DB関数。mergeしたら編集せず追加migrationにする
│   └── tests/           # 制約・RLSの検証（run.sh で最初から再現できる）
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
| POST | `/requests/masking-preview` | LLM送信前の個人情報マスキング確認 |
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

### Claudeによる依頼文の構造化

`CLAUDE_API_ENABLED=true`と`ANTHROPIC_API_KEY`を設定すると、Messages APIの
`structure_request`ツールをJSON Schema付きで強制選択し、自由記述からタイトル、
作業内容、カテゴリ、希望日時、所要時間、概算地域、必要人数、持ち物、注意事項、
危険候補、不足項目を抽出する。接続タイムアウトは`CLAUDE_TIMEOUT_SECONDS`、モデルは
`CLAUDE_MODEL`で設定する。開発時の既定値は外部通信を行わないローカルモックである。

Claudeのtool inputはPydanticモデルで再検証し、不明な項目、範囲外の値、不正な形式を
拒否する。不足項目が複数あっても`additionalQuestion`は先頭の1問だけを返す。
結果は常に`status: draft`、`requiresConfirmation: true`、`autoPublished: false`であり、
ユーザー確認なしに公開しない。モデル名、プロンプト版、処理日時はレスポンスと
本文を含まない監査データへ保存する。

system promptとユーザー本文を別メッセージにし、本文内の命令は依頼内容としてのみ
扱う。APIキー、Claudeの内部エラー、不正な応答内容はレスポンスやログへ出力しない。
環境変数の例はリポジトリルートの`.env.example`を参照する。

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

`requests` 関連のテストは実際の Postgres に接続する（`DATABASE_URL`、既定はローカルの
WSL 上の Postgres）。先に一度用意しておく。

```bash
./supabase/tests/run.sh   # スキーマ適用・制約・RLS の検証。DB を作り直す
python -m pytest -q
```

モックデータを初期状態へ戻す `POST /_mock/reset` は、**全利用者のデータを消す破壊的操作**なので
既定では無効である。利用するには次の2つを両方満たす必要がある。

1. `MOCK_RESET_ENABLED=true` で起動する（開発・テスト環境のみ）
2. 認証済みセッションで呼び出す

この操作はインメモリのストアと Postgres の `requests` を両方リセットする。

```bash
MOCK_RESET_ENABLED=true python -m uvicorn main:app --reload --port 8000
curl -X POST http://localhost:8000/_mock/reset --cookie "$AUTH_COOKIES"
```

無効な環境では、エンドポイントの存在を伏せるため認証の有無にかかわらず404を返す。
テストは `tests/main.py` の冒頭で `MOCK_RESET_ENABLED=true` を設定している。

応募・マッチング・チャット等の業務データ、AI、本人確認はプロセス内だけに保存され、
サーバーを再起動すると初期化される（これらの永続化は #4 の対象外）。
本番環境では認可の細部（RLS のRPC本体、#7 の排他制御等）、CSRF対策、レート制限を
本実装へ置き換えること。
