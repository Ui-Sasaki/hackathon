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

## 確認中

なし。

## 合意済み

なし。
