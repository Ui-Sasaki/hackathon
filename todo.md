# バックエンド・API接続 TODO（2026-08-31更新）

FastAPI実装と`tetote/`からFastAPIへのAPI接続を、1コミットずつレビューできる単位で管理する。画面デザイン、スタイル、アニメーション、端末固有UI、API接続と無関係なReact hooksやlint修正は対象外とする。

## 現在の進捗

- 完了・コミット済み：01〜08（共通APIクライアント、anti-CSRF、共通エラー変換、概算地域APIまで）。
- 応募・マッチ担当の完了・コミット済み：16〜20（17は16のコミットへ同梱、19はPostgres引き継ぎあり）。
- 応募・マッチ担当の次の未着手項目：21（メッセージ一覧API接続）。
- 2026-08-31検証：`tetote/`のテストは49件成功、バックエンドは80件成功。
- TypeScript全体検査：`animated-icon.module.css`と`global.css`の既存型宣言不足により未完了。TODO 16の追加コードに起因するエラーは検出されていない。

## 共通ルール

- [X] 作業前に`git status --short`で既存変更を確認する。
- [X] 既存の未コミット変更を上書きしない。
- [ ] 各項目の実装後、対象差分だけを提示してレビューを待つ。
- [ ] 承認後に対象差分だけをコミットする。
- [ ] 認証・認可、入力検証、個人情報、秘密情報、状態遷移への影響を確認する。
- [ ] API接続で既存の画面デザインや操作感を必要以上に変更しない。

## Push・Pull Requestリマインド

コミットごとにレビューを受け、下記のPR単位が完成するまで原則pushしない。各PRをマージしたら最新`main`から次のブランチを作る。

### PR-01 現在の安定化

対象：01〜04、`AGENTS.md`、`todo.md`

- [ ] 各コミットのレビューが完了している。
- [ ] バックエンドと対象API接続の回帰テストを実行する。
- [ ] `docs/openapi.json`をこのPRへ混ぜていないことを確認する。
- [ ] `git status --short`とPR全体の差分を確認する。
- [ ] ブランチをpushする。
- [ ] 目的、主な変更、検証結果、既知の制約を記載してPRを作成する。

### PR-02 共通APIクライアント

対象：05〜07

- [ ] 05〜07をコミット単位でレビューする。
- [ ] APIクライアントの全テストと型検査を実行する。
- [ ] Cookie、anti-CSRF、秘密情報がログや差分へ露出していないことを確認する。
- [ ] PR全体の差分を確認してpushする。
- [ ] 共通基盤だけを含むPRを作成する。

### PR-03 依頼作成フロー

対象：08〜11

- [ ] 08〜11をコミット単位でレビューする。
- [ ] 地域、マスキング、構造化、作成の一連の接続テストを実行する。
- [ ] 正確な位置情報とマスキング前本文が漏れていないことを確認する。
- [ ] PR全体の差分を確認してpushする。
- [ ] 依頼作成フローだけを含むPRを作成する。

### PR-04 依頼管理フロー

対象：12〜15、32

- [ ] 12〜15と32をコミット単位でレビューする。
- [ ] 一覧、詳細、更新、削除、409再取得の回帰テストを実行する。
- [ ] 固定依頼モックが残っていないことを確認する。
- [ ] PR全体の差分を確認してpushする。
- [ ] 依頼管理フローだけを含むPRを作成する。

### PR-05 応募・マッチ成立

対象：16〜20

- [ ] 16〜20をコミット単位でレビューする。
- [ ] 応募、辞退、一覧、選択、マッチ詳細の回帰テストを実行する。
- [ ] 認可、本人確認、ブロック、楽観ロックを確認する。
- [ ] PR全体の差分を確認してpushする。
- [ ] 応募からマッチ成立までのPRを作成する。

### PR-06 メッセージAPI

対象：21〜22

- [ ] 21〜22をコミット単位でレビューする。
- [ ] 一覧、送信、再送、二重送信、403、404をテストする。
- [ ] sender IDと送信日時をクライアントから送っていないことを確認する。
- [ ] PR全体の差分を確認してpushする。
- [ ] Realtimeを含めずにPRを作成する。

### PR-07 メッセージRealtime

対象：23

- [ ] 23をレビューする。
- [ ] 重複排除、切断、再接続、API再取得をテストする。
- [ ] 書き込みと認可がFastAPI経由のままであることを確認する。
- [ ] PR全体の差分を確認してpushする。
- [ ] RealtimeだけのPRを作成する。

### PR-08 活動完了・評価

対象：24〜28。差分が大きい場合は24〜26と27〜28に分割する。

- [ ] 各コミットをレビューする。
- [ ] 完了、dispute、レビュー、実績生成、公開範囲を回帰テストする。
- [ ] 当事者認可と状態遷移を確認する。
- [ ] PR全体の差分を確認してpushする。
- [ ] 差分量を確認し、必要なら2本のPRへ分割する。
- [ ] 活動完了・評価のPRを作成する。

### PR-09 本人確認

対象：29

- [ ] 29をレビューする。
- [ ] アップロード、秘密情報、申請状態、入力制限を確認する。
- [ ] Supabase担当との合意が必要な範囲を明記する。
- [ ] PR全体の差分を確認してpushする。
- [ ] 本人確認だけのPRを作成する。

### PR-10 通報・ブロック

対象：30〜31

- [ ] 30〜31をコミット単位でレビューする。
- [ ] actor ID、自己ブロック、解除、対象除外をテストする。
- [ ] PR全体の差分を確認してpushする。
- [ ] 安全機能だけのPRを作成する。

### PR-11 最終モック撤去

対象：33

- [ ] 33をレビューする。
- [ ] 応募、マッチ、メッセージの固定データが残っていないことを確認する。
- [ ] ログアウト時の状態クリアと全接続回帰テストを実行する。
- [ ] PR全体の差分を確認してpushする。
- [ ] モック撤去だけのPRを作成する。

### PR-12 APIドキュメント

対象：34〜35

- [ ] 34〜35をコミット単位でレビューする。
- [ ] README、実装、OpenAPIの一致を確認する。
- [ ] OpenAPI一致テストと全バックエンドテストを実行する。
- [ ] PR全体の差分を確認してpushする。
- [ ] ドキュメント同期だけのPRを作成する。

## 完了済み

### 01. 認証済みユーザー解決の復旧

コミット：`c9ac036 fix(auth): restore authenticated user resolution`

- [X] DBレコードから`CurrentUser`を生成する。
- [X] 開発用モック認証を復旧する。
- [X] 未登録・利用停止ユーザーを403で拒否する。
- [X] メール確認、本人確認、MFA状態を反映する。
- [X] 認証テストを成功させる。

### 02. 高危険度通報による依頼停止

コミット：`b317543 fix(reports): suspend requests reported as high risk`

- [X] UUID参照エラーを修正する。
- [X] 通報者をセッションから決定する。
- [X] 高危険度依頼を`suspended`へ遷移させる。
- [X] 通報と監査イベントをテストする。

### 03. 検証済み依頼構造化Service

コミット：`ce1db84 feat(requests): add validated request structuring service`

- [X] Provider、応答検証、監査Repositoryを分離する。
- [X] タイムアウトと最大2回の再試行を実装する。
- [X] JSON SchemaとPydanticで検証する。
- [X] 本文・個人情報を監査Repositoryへ保存しない。
- [X] 自動公開せず、追加質問を1問だけ返す。
- [X] 関連テストを成功させる。

### 04. プロフィールAPI接続

コミット：`064bdd4 feat(frontend): persist editable onboarding profile fields`

- [X] オンボーディングと共通プロフィールをFastAPIへ接続する。
- [X] API連携済みフィールドだけを送信する。
- [X] 認証・入力検証・通信エラーを分類する。
- [X] loading・saving・error状態を反映する。
- [X] 接続テストを成功させる。

## 共通接続基盤

### 05. 共通APIクライアント基盤

コミット：`7d7c52c feat(api-client): add FastAPI client foundation`

- [X] `EXPO_PUBLIC_API_URL`からベースURLを取得する。
- [X] Cookieセッションを全リクエストへ適用する。
- [X] JSONの送受信と共通ヘッダーを実装する。
- [X] タイムアウトとネットワークエラーを型で表現する。
- [X] ユーザーID、ロール、actor ID、送信日時を自動付与しない。
- [X] APIクライアント単体テストを追加する。
- [X] `npm test -- --run`を成功させる。

### 06. anti-CSRFと更新リクエスト

コミット：`dcaa2f3 feat(api-client): support authenticated mutations`

- [X] SuperTokens SDKのanti-CSRF処理を更新リクエストへ適用する。
- [X] Cookieやトークンをログへ出さない。
- [X] GETと更新系の認証動作をテストする。
- [X] セッション期限切れを認証エラーへ変換する。

### 07. APIエラーの共通変換

コミット：`707f822 feat(api-client): map FastAPI errors`

- [X] 共通エラー形式を型定義する。
- [X] 401、403、404、409、422、500を区別する。
- [X] `error.code`、`details`、`requestId`を保持する。
- [X] 非JSON応答や不正なエラー応答を安全に扱う。
- [X] エラー変換の単体テストを追加する。

## 地域と依頼

### 08. 概算地域API接続

コミット：`5877125 feat(location): connect location resolution API`

- [X] `POST /locations/resolve`へ緯度経度または登録地域を送る。
- [X] 取得失敗時は登録地域へフォールバックする。
- [X] 登録地域もない場合のAPIエラーを状態へ反映する。
- [X] 正確な緯度経度を永続化・ログ出力・公開表示しない。
- [X] 成功、拒否、失敗の接続テストを追加する。





### 09. マスキングプレビューAPI接続（実装・テスト済み、未コミット）

想定コミット：`feat(requests): connect masking preview API`

- [X] `POST /requests/masking-preview`へ本文だけを送る。
- [X] マスキング後本文、検出種別、ルール版を保持する。
- [X] 未確認状態では構造化・公開へ進めない。
- [X] 401、422、通信失敗を状態へ反映する。
- [X] 接続テストを追加する。
- [ ] 対象差分のレビュー後、コミットする。

### 10. 依頼構造化API接続

想定コミット：`feat(requests): connect request structuring API`

- [ ] 確認済みのマスキング結果で`POST /requests/structure`を呼ぶ。
- [ ] 追加質問を1問ずつ保持する。
- [ ] 構造化結果を編集可能な下書き状態へ反映する。
- [ ] AI結果だけでは公開しない。
- [ ] 502・503時も手入力へ切り替えられる状態を返す。
- [ ] 接続テストを追加する。

### 11. 依頼作成API接続

想定コミット：`feat(requests): connect request creation API`

- [ ] `POST /requests`へ接続する。
- [ ] 再送中も同じ`Idempotency-Key`を維持する。
- [ ] requester ID、作成日時、初期状態を送らない。
- [ ] 201、409、422、通信失敗をテストする。

### 12. 依頼一覧API接続

想定コミット：`feat(requests): connect request list API`

- [ ] `GET /requests`へ接続する。
- [ ] カテゴリと概算地域フィルターを渡す。
- [ ] loading、empty、error、再試行状態を実装する。
- [ ] 固定依頼一覧を使用しない。
- [ ] 正確な位置情報を状態へ保持しない。
- [ ] 接続テストを追加する。

### 13. 依頼詳細API接続

想定コミット：`feat(requests): connect request detail API`

- [ ] `GET /requests/{id}`へ接続する。
- [ ] 404と通信失敗を区別する。
- [ ] APIレスポンスのIDとversionを保持する。
- [ ] 接続テストを追加する。

### 14. 依頼更新API接続

想定コミット：`feat(requests): connect request update API`

- [ ] `PATCH /requests/{id}`へ接続する。
- [ ] `expectedVersion`を送る。
- [ ] requester IDや更新日時を送らない。
- [ ] 409時に最新データを再取得できる状態へする。
- [ ] 403、404、409、422をテストする。

### 15. 依頼削除API接続

想定コミット：`feat(requests): connect request deletion API`

- [ ] `DELETE /requests/{id}`へ接続する。
- [ ] 成功後に対象依頼を接続側状態から除外する。
- [ ] 403、404、409と重複操作をテストする。

## 応募とマッチ

### 16. 応募作成API接続（完了）

コミット：`d6ae754 feat(applications): connect application creation API`

- [X] `POST /requests/{id}/applications`へ応募理由と対応可能日時だけを送る。
- [X] helper ID、応募日時、状態を送らない。
- [X] 自己応募、重複、期限切れ、募集終了、本人確認不足を反映する。
- [X] 接続テストを追加する。
- [X] 対象差分のレビュー後、コミットする。

### 17. 応募辞退API接続（完了、TODO 16へ同梱）

コミット：`d6ae754 feat(applications): connect application creation API`

- [X] `POST /applications/{id}/withdraw`へ接続する。
- [X] 成功後に応募状態をサーバーレスポンスで更新する。
- [X] 403、404、409、重複辞退をテストする。

### 18. 応募者一覧API接続（完了）

コミット：`94f8dac feat(applications): connect applicant list API`

- [X] `GET /requests/{id}/applications`へ接続する。
- [X] 依頼所有者以外の403を扱う。
- [X] ブロックされた利用者をAPI結果に従って除外する。
- [X] loading、empty、errorをテストする。

### 19. 応募者選択API接続（完了、Postgres引き継ぎあり）

コミット：`1d048f1 feat(applications): connect applicant selection API`

- [X] `POST /applications/{id}/select`へ`expectedVersion`を送る。
- [X] 成功レスポンスのマッチIDとversionを保持する。
- [X] 403、404、409をテストする。

### 20. マッチ詳細API接続（完了）

コミット：`64bd39e feat(matches): connect match detail API`

- [X] `GET /matches/{id}`へ接続する。
- [X] 当事者以外の403と存在を伏せる404を扱う。
- [X] マッチ状態とversionを保持する。
- [X] 接続テストを追加する。

## メッセージ

### 21. メッセージ一覧API接続

想定コミット：`feat(messages): connect message list API`

- [ ] `GET /matches/{id}/messages`へ接続する。
- [ ] APIレスポンスのsender IDと送信日時を保持する。
- [ ] ページング、empty、403、404を扱う。
- [ ] 接続テストを追加する。

### 22. メッセージ送信API接続

想定コミット：`feat(messages): connect message sending API`

- [ ] `POST /matches/{id}/messages`へ本文だけを送る。
- [ ] sender IDと送信日時を送らない。
- [ ] 送信中、失敗、再送、二重送信防止を扱う。
- [ ] 403、404、422をテストする。

### 23. メッセージRealtime同期

想定コミット：`feat(messages): reconcile realtime messages`

- [ ] FastAPI取得結果とRealtimeイベントをIDで重複排除する。
- [ ] 対象マッチのメッセージだけを反映する。
- [ ] 切断時に再取得へフォールバックする。
- [ ] 書き込みと認可はFastAPI経由のまま維持する。
- [ ] 同期テストを追加する。

## 完了・レビュー・実績

### 24. 完了確認API接続

想定コミット：`feat(matches): connect completion API`

- [ ] `POST /matches/{id}/complete`へ接続する。
- [ ] `completion_pending`と`completed`をレスポンスから反映する。
- [ ] 重複完了と不正状態の409を扱う。
- [ ] 接続テストを追加する。

### 25. dispute API接続

想定コミット：`feat(matches): connect dispute API`

- [ ] `POST /matches/{id}/dispute`へ理由だけを送る。
- [ ] actor IDや申請日時を送らない。
- [ ] 403、404、409、422をテストする。

### 26. レビュー投稿API接続

想定コミット：`feat(reviews): connect review API`

- [ ] `POST /matches/{id}/reviews`へ選択式評価とコメントだけを送る。
- [ ] reviewer ID、reviewee ID、投稿日時を送らない。
- [ ] 未完了、重複、422を扱う。
- [ ] 接続テストを追加する。

### 27. 実績生成API接続

想定コミット：`feat(achievements): connect generation API`

- [ ] `POST /achievements/generate`へ接続する。
- [ ] AI生成結果と累計実績をレスポンスから保持する。
- [ ] 完了済み活動だけが対象であることをAPIテストで確認する。
- [ ] 403、409、502、503を扱う。

### 28. 実績公開範囲API接続

想定コミット：`feat(achievements): connect visibility API`

- [ ] `PATCH /achievements/visibility`へ接続する。
- [ ] 本人承認前のpublic変更を許可しない。
- [ ] 403、409、422をテストする。

## 本人確認と安全機能

### 29. 本人確認申請API接続

想定コミット：`feat(verifications): connect application API`

- [ ] 安全な画像アップロードAPIの有無を確認する。
- [ ] Service Role Keyや秘密鍵をクライアントへ置かない。
- [ ] `POST /verifications`へAPIが受け付ける参照だけを送る。
- [ ] `emailVerified`と`verificationStatus`を別々に保持する。
- [ ] pending中の重複、413、415、422を扱う。

### 30. 通報API接続

想定コミット：`feat(safety): connect reporting API`

- [ ] `POST /reports`へ対象、理由、説明だけを送る。
- [ ] reporter ID、severity、状態、日時を送らない。
- [ ] 401、404、422をテストする。

### 31. ブロックAPI接続

想定コミット：`feat(safety): connect blocking API`

- [ ] `POST /users/{id}/block`へ接続する。
- [ ] ブロックと解除を扱う。
- [ ] actor IDを送らない。
- [ ] 成功後はAPI結果に従って対象業務データを除外する。
- [ ] 自己ブロック、404、422をテストする。

## モック撤去とドキュメント

### 32. 依頼固定モック撤去

想定コミット：`refactor(requests): remove fixed request mocks`

- [ ] `RequestsContext`の固定依頼データを削除する。
- [ ] 依頼API由来の状態へ置き換える。
- [ ] 認証切れ・ログアウト時に依頼状態をクリアする。
- [ ] 接続回帰テストを追加する。

### 33. 応募・マッチ・メッセージ固定モック撤去

想定コミット：`refactor(matches): remove fixed interaction mocks`

- [ ] 固定の応募、マッチ、メッセージデータを削除する。
- [ ] APIレスポンスのIDとversionを画面間で維持する。
- [ ] 認証切れ・ログアウト時に業務状態をクリアする。
- [ ] 接続回帰テストを追加する。

### 34. README実装状況同期

想定コミット：`docs(api): synchronize implementation status`

- [ ] 実装済み、Memory Repository、Postgres実装の記述をコードと一致させる。
- [ ] API接続済み範囲と未接続範囲を明記する。
- [ ] 既知の制約とSupabase担当への引き継ぎを記載する。

### 35. OpenAPI同期

想定コミット：`docs(api): regenerate OpenAPI contract`

- [ ] FastAPIアプリから`docs/openapi.json`を再生成する。
- [ ] 秘密情報や内部専用フィールドが露出していないことを確認する。
- [ ] `.venv/bin/python -m pytest -q tests/test_openapi.py`を成功させる。

### 36. 最終回帰検証

コミットなし。

- [ ] `.venv/bin/python -m pytest -q`を成功させる。
- [ ] API接続に関係する`tetote/`のテストを成功させる。
- [ ] API接続に関係するTypeScript検査を成功させる。
- [ ] `git diff --check`を成功させる。
- [ ] `git status --short`で未コミット差分を確認する。
