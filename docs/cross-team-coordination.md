# フロントエンド・DB担当との調整事項

FastAPI実装やAPI接続だけでは確定できない事項を記録する。仕様、UI、API契約、永続化方式に影響する判断は、担当者と合意するまで未決定として扱う。

## 記載項目

- 対象TODOと機能
- 調整先
- 現状とずれ
- 確認・決定が必要な内容
- FastAPI担当側で完了している範囲
- 接続・引き継ぎ条件
- 状態（未確認、確認中、合意済み）

## 未確認

### COORD-006: 自分の依頼・マッチ一覧API

- 対象: 依頼一覧・詳細・更新・取消、マッチ詳細への画面導線
- 調整先: FastAPI担当、Supabase担当
- 現状とずれ:
  - `GET /requests` は公開依頼の検索APIであり、依頼者本人の `pending_review`、`matched`、`completed`、`cancelled` などを一括取得する契約がない。
  - `GET /matches` の共通契約、Memory Repository、APIテスト、画面接続を追加した。
  - Postgres Repositoryと `app.list_own_chat_matches()` を追加し、当事者認可とブロック除外をDBでも保証した。
  - 接続側は公開一覧に含まれる自分の依頼から、詳細・更新・取消・応募者一覧・応募者選択へ進める範囲まで実装した。
- 確認・決定が必要な内容:
  - `GET /me/requests` 相当の状態フィルタ・カーソル・表示項目。
  - 本番Supabaseへ `20260904040000_chat_list_persistence.sql` を適用する手順と時期。
  - ブロック済み利用者に関する一覧除外と、完了・紛争中データの保持期間。
- 接続・引き継ぎ条件:
  - actor IDはクエリで受け取らず、検証済みセッションから決定する。
  - 一覧レスポンスに `requestId`、`matchId`、`version` を含め、既存の詳細・チャット・楽観ロックへ引き継げるようにする。
- 状態: 実装済み（本番migration適用は人間の承認待ち）

### COORD-005: 本番の認証ユーザープロフィール自動作成

- 対象: 公開環境の `GET /profile` が新規登録直後に403を返す問題
- 調整先: Supabase担当、デプロイ担当
- 現状とずれ:
  - FastAPIはSuperTokensのsubjectを`app.resolve_authenticated_user`へ渡し、アプリ側プロフィールを解決する。
  - `20260903040000_identity_profile_persistence.sql`では、未登録subjectを安全な既定値（`member`、`active`）で自動作成する。
  - 公開環境で`USER_PROFILE_NOT_FOUND`が返る場合、APIコードと本番DB migrationの適用状態が一致していない。
- FastAPI・接続側で完了している範囲:
  - クライアント入力のユーザーIDやroleを信用せず、検証済みセッションsubjectだけを使用する。
  - 認証復元完了前に依頼APIを呼ばないため、初期401とセッション復元の競合を防止する。
  - Memory RepositoryとPostgres Repositoryで同じプロフィールAPI契約を提供する。
- 接続・引き継ぎ条件:
  - 本番Supabaseへ`20260903040000_identity_profile_persistence.sql`までを順番どおり適用する。
  - 適用後、新規アカウントで登録し、`GET /profile`が200、続く`GET /requests`が200になることを確認する。
  - 既存アカウントが403の場合はレスポンスの`error.code`を確認し、`USER_SUSPENDED`を自動解除しない。
- 状態: 未確認（コード実装済み、本番migration適用と結合確認待ち）

### COORD-003: 応募者選択のPostgres原子操作（実装済み）

- 対象TODO: 19 応募者選択API接続
- 調整先: Supabase担当
- 現状とずれ:
  - API契約は応募IDと`expectedVersion`から、応募選択、定員予約、依頼状態更新、未選択応募終了、マッチ作成を一体で行う必要がある。
  - 既存Postgres Repositoryには、この一連の操作を同一トランザクションで実行するメソッドがない。
  - FastAPIから複数のPostgres更新を個別に呼ぶと、複数端末からの同時選択時に定員超過や部分更新が起こり得る。
- FastAPI担当側で完了する範囲:
  - クライアント入力を`expectedVersion`だけに制限する。
  - 所有者、ブロック関係、応募状態、定員、楽観ロックを検証するService。
  - `ApplicationRepository.select`と`RequestRepository.reserve_helper`の共通契約。
  - Memory Repository、API接続、認可・競合テスト。
  - Postgres側の操作が未実装なら503で拒否し、不完全な更新を実行しない。
- 接続・引き継ぎ条件:
  - 応募ID、依頼者、`expectedVersion`を検証し、応募状態更新、定員予約、依頼状態更新、未選択応募終了、マッチ作成を単一トランザクションまたはPostgreSQL関数で行う。
  - version不一致、定員到達、選択済み応募は409へ変換できる結果を返す。
  - ブロック関係と依頼所有者はFastAPIでも引き続き検証する。
- 実装結果:
  - `app.select_application(uuid, integer)`が依頼行をロックし、応募選択、定員予約、match作成、依頼更新、残応募終了を同一transactionで行う。
  - `PostgresApplicationRepository.select_atomically`がRPCを呼び、FastAPIが結果コードを403/404/409へ変換する。
  - migration、RLS経由のDBテスト、複数接続による同時選択テストを追加した。
- 状態: 実装済み（Production適用は人間の承認待ち）

### COORD-001: 位置情報利用の明示同意UI

- 対象TODO: 08 概算地域API接続
- 調整先: フロントエンド担当
- 現状とずれ:
  - 要件では、ユーザーの許可後にGPSから現在地を取得する。
  - 現在の依頼入力画面には「現在地を使用する」などの明示同意UIがない。
  - 画面表示だけで自動的にブラウザの位置情報許可を要求すると、明示同意の要件と既存の操作感に影響する。
- 確認・決定が必要な内容:
  - 同意UIの配置、文言、初期状態、再試行導線。
  - 拒否時と取得失敗時に、登録地域を使用したことを画面へ表示する方法。
  - 登録地域もない場合のエラー表示と地域登録への導線。
- FastAPI担当側で完了する範囲:
  - `POST /locations/resolve`を呼ぶService。
  - 同意済み座標、拒否、タイムアウト、未対応の入力変換。
  - APIレスポンスから概算地域だけを保持し、正確な座標を状態へ残さない処理。
  - 成功、拒否、取得失敗、登録地域なしの接続テスト。
- 接続・引き継ぎ条件:
  - UIは明示的な同意結果をServiceの`consentGranted`へ渡す。
  - `resolved`時は`areaCode`と`areaLabel`を依頼作成フローへ引き継ぐ。
  - `fallbackUsed`が`true`の場合は登録地域を使用した旨を表示する。
  - `error`時は共通`ApiError`を既存のエラー表示へ反映する。
- 状態: 未確認（Serviceとテストのみ先行し、UI接続は保留）

### COORD-002: iOSネイティブ対応

- 対象TODO: 現行TODOの対象外
- 調整先: フロントエンド担当、認証担当、インフラ担当
- 現状とずれ:
  - 現行要件はレスポンシブWebアプリをMVP対象とし、ネイティブiOSアプリは対象外としている。
  - 現在の認証は`supertokens-web-js`、HttpOnly Cookie、anti-CSRFを前提としている。
  - 現在地取得はWeb向けの`navigator.geolocation`を使用する。
- 確認・決定が必要な内容:
  - SuperTokensのiOS向けセッション管理と、FastAPIでCookie認証とBearer認証を併用するか。
  - `expo-location`、iOS権限文言、実機での拒否・再許可導線。
  - Supabase Realtimeのネイティブ認証、Push通知、EAS Build、署名、App Store公開の担当範囲。
- 当面の方針:
  - MVPはiPhone Safariを含むWeb版として開発を継続する。
  - FastAPIの業務API契約は、将来のネイティブクライアントからも利用できる形を維持する。
  - iOS固有の認証、位置情報取得、権限設定は、関係担当者との合意前に実装しない。
- 接続・引き継ぎ条件:
  - 位置情報Serviceは取得元を注入可能なまま維持し、将来Web用とNative用に分離できるようにする。
  - 認証方式を変更しても、ユーザーID、ロール、actor ID、送信日時をクライアント入力から受け取らない。
- 状態: 未確認（当面はWeb版を対象とする）

### COORD-003: 危険度判定結果の画面表示

- 対象TODO: Issue #30 危険度判定
- 調整先: フロントエンド担当
- 現状とずれ:
  - 要件定義書 11.2 の危険度は `low`、`medium`、`high`、`prohibited` の4段階である。
  - Issue #30 は `low`、`review_required`、`high` の語彙で書かれており、`high` を公開拒否としている。
  - 本実装は要件定義書の語彙を `riskLevel` に残し、公開可否を `decision`
    (`publish`、`publish_with_warning`、`pending_review`、`rejected`) として分けた。
  - 依頼入力画面のプレースホルダーが「代わりに近所のスーパーに行ってほしい」であり、
    要件定義書 3.4 で MVP 対象外とされる買い物代行に近い例になっている。
    現在の固定ルールはこの言い回しを検出しないため、例示を変えるか、
    検出語を広げるかの判断が必要である。
- 確認・決定が必要な内容:
  - 禁止判定 (`rejected`) を利用者へ伝える文言と、入力し直しへの導線。
  - 管理者審査 (`pending_review`) 中であることの表示と、公開されるまでの案内。
  - `publish_with_warning` の注意事項をどの画面のどこへ表示するか。
  - 依頼入力画面のプレースホルダー文言を、MVP対象外にあたらない例へ差し替えるか。
- FastAPI担当側で完了している範囲:
  - 固定ルールとLLMを併用する判定サービスと、判定根拠の監査項目。
  - `POST /requests/structure` と `POST /requests` への接続。
  - 境界値、固定ルールとLLMの競合、LLM障害時のテスト。
- 接続・引き継ぎ条件:
  - 画面は `decision` で分岐し、`riskLevel` を直接判定条件にしない。
  - 禁止時は `422 PROHIBITED_REQUEST` の `details.messages` をそのまま表示できる。
  - `warnings` は利用者へ表示して差し支えない文言だけを含む。
- 状態: 未確認（APIとテストのみ先行し、画面表示は保留）

### COORD-004: 画像の保存先と削除期限

- 対象TODO: Issue #83 プロフィール画像アップロードAPI
- 調整先: ストレージ担当、Supabase担当
- 現状とずれ:
  - 要件では本人確認画像を非公開Storageへ置き、定期処理で削除する。
  - 現在の実装は `MemoryUploadRepository` だけで、画像をプロセス内に保持している。
  - `POST /verifications` は依然としてクライアントから `storageObjectKey` を受け取る契約であり、
    ストレージ内部キーをクライアントへ置かない方針と矛盾している（Issue #86で扱う）。
- 確認・決定が必要な内容:
  - Supabase Storage のバケット構成と、署名付きURLの発行方式・有効期限。
  - `uploads` と `images` に相当するテーブル定義とRLSポリシー。
  - プロフィール画像と本人確認画像それぞれの保持期間と削除タイミング。
  - マルウェア対策をどの層で行うか（Storage側のスキャン、または受信時）。
  - 配信をアプリ経由のままにするか、署名付きURLへ切り替えるか。切り替える場合のキャッシュ方針。
- FastAPI担当側で完了している範囲:
  - MIME type、拡張子、サイズ、画像実体のサーバー側検証。
  - JPEGとPNGのメタデータ除去。
  - 期限付きアップロード、未使用アップロードの回収、差し替え失敗時の既存画像保持。
  - 推測できない参照子による配信と、用途違いの画像を配信しない制御。
  - 401、404、409、413、415、422 のテスト。
- 接続・引き継ぎ条件:
  - 画面は `uploadId` と `imageUrl` だけを扱い、ストレージ内部キーを保持しない。
  - `UploadRepository` Protocol を満たす実装へ差し替えれば、公開契約は変わらない。
- 状態: 未確認（Memory実装とテストのみ先行し、Storage・Postgresは保留）

## 確認中

なし。

## 合意済み

なし。
