# テトテFastAPI 開発ガイド

地域の困りごとと支援者をつなぐAPIである。認証・セッション管理にはSuperTokensを使う。依頼、応募、マッチ、チャット、完了処理、プロフィール、利用者設定、依頼保存・非表示、構造化監査、ブロック、通報、本人確認申請の保存先はRepositoryで分離され、開発・テストではメモリ、本番ではSupabase PostgreSQLを使う。レビュー、AI実績は現在インメモリで模擬している。

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
- 固定OpenAPI: `docs/openapi.json`
- ヘルスチェック: `http://localhost:8000/health`

起動前にSuperTokens Coreを用意し、必要に応じて次の環境変数を設定する。

| 環境変数 | 既定値 | 用途 |
|---|---|---|
| `SUPERTOKENS_CONNECTION_URI` | `http://localhost:3567` | SuperTokens Core接続先 |
| `SUPERTOKENS_API_KEY` | 未設定 | Core APIキー |
| `API_DOMAIN` | `http://localhost:8000` | API公開元 |
| `WEBSITE_DOMAIN` | `http://localhost:3000` | CORSで許可するフロントエンド |
| `AUTH_COOKIE_SECURE` | `true` | CookieのSecure属性 |
| `AUTH_COOKIE_SAME_SITE` | 自動 | CookieのSameSite属性。未指定時はAPIとフロントが別オリジンかつSecure Cookieなら`none`、それ以外は`lax` |
| `AUTH_MOCK_ENABLED` | `false` | 開発用の認証モックを有効化。**本番では有効にできない**（起動時に拒否） |
| `AUTH_MOCK_USER_ID` | `usr_101` | 認証モックの既定ユーザーID |
| `MOCK_RESET_ENABLED` | `false` | `POST /_mock/reset` を利用可能にする。**本番では有効にできない**（起動時に拒否） |
| `APP_ENV` | `development` | `production` の場合はPostgresを強制し、Memory指定を拒否する |
| `REQUEST_REPOSITORY` | `memory` | 非本番での依頼保存先。`memory` または `postgres` |
| `DATABASE_URL` | 未設定 | Postgres選択時は必須。Supabaseの接続文字列 |

`APP_ENV=production` では、認証や運用の安全装置を外す設定を起動時に拒否する。
`AUTH_MOCK_ENABLED=true`、`MOCK_RESET_ENABLED=true`、`SUPERTOKENS_ENABLED=false` の
いずれかが設定されているとアプリは起動しない。黙って無効化せず起動を止めるのは、
設定した本人が気づけないまま公開されるのを防ぐためである。

本番は `APP_ENV=production` と `DATABASE_URL` を必ず設定する。本番では
`REQUEST_REPOSITORY` の省略時もPostgresが選ばれ、接続情報がなければアプリのimport時に
失敗する。Memory Repositoryへ暗黙にフォールバックしない。

登録、ログイン、ログアウト、パスワード再設定はSuperTokensの`/auth/*` APIを
利用する。Cookie認証ではHttpOnly/Secure/SameSite Cookieと`anti-csrf`ヘッダーが
使われる。ローカルHTTP開発時だけ`AUTH_COOKIE_SECURE=false`にする。
Vercelの別プロジェクトなどAPIとフロントが別オリジンの場合、ブラウザの`fetch`へ
セッションCookieを載せるため、未指定時は`AUTH_COOKIE_SAME_SITE=none`相当にする。
本番では検証済みSuperTokens subjectを初回の業務APIアクセス時にPostgresへ安全な
`member`・未確認状態で登録する。再認証時に既存のプロフィール、role、本人確認状態を
上書きしない。Memory構成では登録成功時に同等の初期プロフィールを作成する。

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
│   ├── repositories/    # requestsの保存インターフェースとMemory/Postgres実装
│   ├── services/        # 保存方式に依存しない依頼の認可・状態遷移
│   ├── settings.py      # Repository切り替えを含む実行設定
│   ├── cruds/main.py    # エンドポイント（他業務データはインメモリ）
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
| POST | `/locations/resolve` | 現在地の概算地域化・登録地域フォールバック |
| POST | `/requests/structure` | 依頼文の構造化 |
| POST | `/requests/masking-preview` | LLM送信前の個人情報マスキング確認 |
| GET / POST | `/requests` | 依頼一覧・作成 |
| GET / PATCH / DELETE | `/requests/{id}` | 依頼取得・更新・取消 |
| POST | `/requests/{id}/applications` | 依頼への応募 |
| GET | `/requests/{id}/applications` | 応募者一覧 |
| POST | `/applications/{id}/select` | 応募者選択 |
| POST | `/applications/{id}/withdraw` | 応募取り下げ |
| GET | `/matches` | 自分のチャット一覧（最新メッセージ・未読数） |
| GET / POST | `/matches/{id}/messages` | チャット取得・送信 |
| POST | `/matches/{id}/complete` | 完了確認 |
| POST | `/matches/{id}/dispute` | マッチングキャンセル |
| POST | `/matches/{id}/reviews` | 評価投稿 |
| POST | `/achievements/generate` | 実績生成 |
| POST | `/verifications` | 本人確認申請 |
| POST | `/reports` | 通報 |
| POST | `/users/{id}/block` | ブロック・解除 |

`PATCH /profile`は既存フロントエンドのプロフィール入力を基準に、表示名、都道府県、
年代、注意事項、支援者区分、大学・学部・学年、職業・業界・勤務先、性別、興味、
一言メッセージを更新する。本人ID、ロール、メール確認、本人確認状態はセッションと
サーバー側レコードから決定し、クライアント入力では変更できない。プロフィール画像は
安全なアップロードAPIが未実装のため、端末ローカルURIを`PATCH /profile`へ送らない。

詳細なリクエスト・レスポンス仕様はSwagger UIを参照する。
認証、モック利用者、ページング、実装状況を含むフロント向け手順は
[`docs/api-development.md`](../docs/api-development.md)を参照する。固定OpenAPIは
手編集せず、リポジトリルートで次を実行してFastAPIアプリから再生成する。

```bash
.venv/bin/python scripts/export_openapi.py
```

### 位置情報の利用と保存

位置情報は依頼作成時の概算地域への変換と依頼一覧の距離順表示にだけ利用する。
画面側は利用目的を表示し、ユーザーが現在地利用を選択してブラウザ権限を許可した後に
のみ取得する。APIへ座標を送る場合は `consentGranted: true` が必須である。

`POST /locations/resolve` は座標を検証して地域コードへ変換する。拒否、タイムアウト、
ブラウザ非対応、取得失敗の場合は `failureReason` に `denied`、`timeout`、
`unsupported`、`unavailable` のいずれかを指定し、認証ユーザーの登録地域を使う。
登録地域もない場合は `REGION_SELECTION_REQUIRED` を返すため、画面側で地域選択へ
案内する。正確な座標は処理中だけ使用し、DB、公開レスポンス、ログには保存・出力
しない。常時追跡、バックグラウンド取得、行動履歴の保存は行わない。

### LLM入力の個人情報マスキング

依頼文はLLMへ渡す前に、メールアドレス、電話番号、郵便番号、詳細住所、証明書番号、
「氏名」「名前」と明記された日本語氏名を種別付きプレースホルダーへ置換する。
半角・全角の数字、記号、代表的な日本語住所表記に対応する。検出した元の値は
ログ、例外、監視カウンター、マスキング結果へ複製しない。

`POST /requests/masking-preview`でマスキング後の本文、種別、件数を確認できる。
個人情報が検出された状態で構造化すると、LLMを呼ばず確認要求を返す。ユーザーは
誤検出なら元の入力を修正し、妥当なら`maskingConfirmed: true`で再送する。構造化
クライアントへ渡るのは常にマスキング後の本文だけである。

この固定ルールは代表的な形式を検出する補助機能であり、完全な匿名化を保証しない。
固有名詞、崩した表記、文脈から推測できる情報は検出できない場合があるため、送信前に
ユーザー自身がマスキング結果を確認する必要がある。

### Claudeによる依頼構造化

既定の`CLAUDE_API_ENABLED=false`では外部通信をせず、開発用のローカルProviderを
使う。Claudeを使う場合は`CLAUDE_API_ENABLED=true`と`ANTHROPIC_API_KEY`を設定する。
Messages APIにはタイムアウトを設定し、JSON Schemaを指定した
`structure_request`ツールだけを選択させたうえで、tool inputをPydanticでも再検証する。

応答は常に`status: draft`、`requiresConfirmation: true`、`autoPublished: false`で、
ユーザー確認なしに公開されない。監査用Repositoryにはモデル名、プロンプト版、
処理日時、スキーマ版だけを保存し、依頼本文やマスキング前の個人情報は保存しない。
本番ではPostgresへ永続化し、管理者だけが監査メタデータを参照できる。

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

通常の単体テスト・APIテストはMemory Repositoryを使い、Postgresや外部Supabaseへ接続しない。

```bash
.venv/bin/python -m pytest -q
```

Postgres固有の制約、RLS、トランザクション境界はDB結合テストとして分離している。
外部Supabaseではなく、破棄可能なローカルPostgresに対して次を実行する。このスクリプトは
対象DBを作り直すため、共有DBや本番の接続先を指定しないこと。

```bash
./supabase/tests/run.sh

# APIをPostgres Repositoryで手動確認する場合
APP_ENV=development \
REQUEST_REPOSITORY=postgres \
DATABASE_URL='postgresql://tetote_app@127.0.0.1:55432/tetote?sslmode=disable' \
MOCK_RESET_ENABLED=true \
.venv/bin/python -m uvicorn main:app --port 8000
```

モックデータを初期状態へ戻す `POST /_mock/reset` は、**全利用者のデータを消す破壊的操作**なので
既定では無効である。利用するには次の2つを両方満たす必要がある。

1. `MOCK_RESET_ENABLED=true` で起動する（開発・テスト環境のみ）
2. 認証済みセッションで呼び出す

この操作はインメモリの業務ストアと、現在選択されている依頼Repositoryをリセットする。

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
