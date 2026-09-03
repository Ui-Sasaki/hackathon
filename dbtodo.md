# Supabase 必須実装 TODO

更新日: 2026-09-03

## 作業ルール

- [ ] 作業開始前と完了前に `git status --short` を確認する。
- [ ] migrationは既存ファイルを書き換えず、forward-onlyで追加する。
- [ ] Memory RepositoryとPostgres RepositoryのAPI契約を一致させる。
- [ ] 認証・認可、RLS、状態遷移、競合、監査ログをDBテストで確認する。
- [ ] 各項目の完了後に `.venv/bin/python -m pytest -q` と `supabase/tests/run.sh` を実行する。
- [ ] Production Supabaseへのmigration適用とdeployは、人間の承認後に行う。

## 必須10項目

### 01. 応募者選択の原子処理

関連Draft: [#64](https://github.com/Ui-Sasaki/hackathon/pull/64)

- [x] 応募ID、依頼所有者、`expectedVersion`を検証する。
- [x] 応募選択、定員予約、マッチ作成、依頼状態更新を同一transactionで行う。
- [x] 定員到達時に未選択応募を終了する。
- [x] 二重選択、version競合、定員超過を409へ変換できる結果を返す。
- [x] 複数接続による同時選択テストを成功させる。

### 02. マッチ情報の永続化

関連Draft: [#64](https://github.com/Ui-Sasaki/hackathon/pull/64)

- [x] `MatchRepository`のPostgres実装を統合する。
- [x] 依頼者と選択された支援者だけが取得できるようにする。
- [x] ブロック関係と利用停止状態を検証する。
- [x] match、application、requestの状態を不整合なく保存する。

### 03. チャットメッセージの永続化

関連Draft: [#64](https://github.com/Ui-Sasaki/hackathon/pull/64)

- [x] メッセージ一覧と送信をPostgresへ接続する。
- [x] sender IDと送信日時をサーバーで決定する。
- [x] マッチ当事者以外の取得・送信を拒否する。
- [x] ブロック後の送信を拒否し、閲覧範囲へ反映する。
- [x] 既読状態を保存する。

### 04. 完了確認・disputeの原子処理

関連Draft: [#64](https://github.com/Ui-Sasaki/hackathon/pull/64)

- [x] 依頼者と支援者の完了確認を個別に保存する。
- [x] 片方のみの場合は`completion_pending`へ遷移する。
- [x] 双方確認後にmatchとrequestを`completed`へ遷移する。
- [x] dispute時にmatch、request、監査ログを同一transactionで更新する。
- [x] 重複操作と不正な状態遷移を409で拒否する。

### 05. 認証ユーザーとDBユーザーの正規連携

関連Draft: [#68](https://github.com/Ui-Sasaki/hackathon/pull/68)

- [x] SuperTokens subjectから内部の`users.id`を解決する。
- [x] role、利用停止、メール確認、本人確認状態をDBから取得する。
- [x] 再認証時にプロフィール情報を上書きしない。
- [x] actor contextなしの業務クエリをRLSで拒否する。
- [ ] 実SuperTokensとの結合確認を行う。

### 06. プロフィールの永続化

関連Draft: [#68](https://github.com/Ui-Sasaki/hackathon/pull/68)

- [x] Profile RepositoryのPostgres実装を統合する。
- [x] 本人だけがプロフィールを更新できるようにする。
- [x] role、本人確認状態などの保護フィールドを更新入力から除外する。
- [x] 活動地域マスタとプロフィール項目の制約を適用する。
- [x] 公開プロフィールへ機微情報を含めない。

### 07. ブロック関係の永続化

関連Draft: [#69](https://github.com/Ui-Sasaki/hackathon/pull/69)

- [ ] ブロックと解除をPostgresへ保存する。
- [ ] 自己ブロックと存在しない対象を拒否する。
- [ ] ブロック関係と監査ログを同一transactionで更新する。
- [ ] 依頼、応募、マッチ、メッセージの取得・送信へ反映する。
- [ ] ブロックと解除を冪等にする。

### 08. 通報と依頼停止の永続化

- [ ] Report RepositoryのPostgres実装を追加する。
- [ ] 通報対象の存在と閲覧権限を検証する。
- [ ] reporter IDを認証セッションから決定する。
- [ ] high risk依頼の停止と監査ログを同一transactionで保存する。
- [ ] 管理者による調査、解決、却下の状態遷移を実装する。

### 09. 本人確認申請と証明画像管理

- [ ] Verification RepositoryのPostgres実装を追加する。
- [ ] 審査中申請の重複を禁止する。
- [ ] private Storage bucketとStorage policyを設定する。
- [ ] クライアントへStorageの直接参照権限を与えない。
- [ ] 担当者だけが短時間有効な署名URLを取得できるようにする。
- [ ] 承認・否認、利用者状態、監査ログを原子的に更新する。
- [ ] 承認・否認後7日以内に画像を削除するjobを実装する。

### 10. レビューと実績プロフィールの永続化

- [ ] Review RepositoryとAchievement RepositoryのPostgres実装を追加する。
- [ ] completedマッチの当事者だけが相手へレビューできるようにする。
- [ ] 同一マッチにつき各ユーザー1件に制限する。
- [ ] AI生成結果、モデル名、prompt version、生成日時を保存する。
- [ ] 本人承認前のpublic公開を拒否する。
- [ ] 公開範囲の更新と監査ログを保存する。

## Draft統合順

- [ ] #64を最新`main`へ載せ替えて統合する。
- [ ] #66を#64統合後の構成へ載せ替えて統合する。
- [ ] #68と#69を順番に載せ替え、兄弟stacked PRの重複差分を除く。
- [ ] migrationの適用順と関数名の競合がないことを確認する。
- [ ] `todo.md`、`docs/api-development.md`、`docs/cross-team-coordination.md`を実装状況に合わせて更新する。

## 完了条件

- [ ] 上記10項目が本番設定でMemory Repositoryへフォールバックしない。
- [ ] APIとRLSの両方で所有者、当事者、role、利用停止、ブロック状態を検証する。
- [ ] APIテスト、DB制約テスト、RLSテスト、同時実行テストが成功する。
- [ ] Production適用手順、既知の制約、corrective migrationによる復旧方針をPRへ記載する。
