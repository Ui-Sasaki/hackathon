# Supabase 実装状況と不足一覧

調査日: 2026-09-03  
調査対象ブランチ: `db`（`feature/react-native-api-integration` の先頭から作成）

## 判定基準

- 「現行実装」は、このブランチのコードからFastAPIがPostgresを選択して利用できる状態を指す。
- baseline migrationにテーブル、制約、RLSが存在するだけでは「永続化実装済み」と判定しない。
- 「Draft実装あり」はGitHubのopen Draft PRにコード、migration、DBテストがあるが、現行ブランチへ未統合の状態を指す。
- Production Supabaseへのmigration適用、環境変数設定、deployは各Draft PRの対象外である。

## GitHub Draft PR

| PR | 内容 | DB実装の扱い | 依存関係・注意点 |
|---|---|---|---|
| [#64](https://github.com/Ui-Sasaki/hackathon/pull/64) | 応募者選択、マッチ、チャット、完了確認、dispute、依頼取消 | Draft実装あり | `main`向け。`20260823000000_matching_persistence.sql`、`MatchRepository`、DB結合・同時実行テストを含む |
| [#66](https://github.com/Ui-Sasaki/hackathon/pull/66) | FastAPI router分割 | DB機能追加なし | #64をbaseにする。後続Draftの土台 |
| [#68](https://github.com/Ui-Sasaki/hackathon/pull/68) | 認証subject解決、プロフィール、活動地域 | Draft実装あり | #66をbaseにする。`20260827000000_profile_persistence.sql`を含む |
| [#69](https://github.com/Ui-Sasaki/hackathon/pull/69) | ブロック・解除、監査ログ | Draft実装あり | #66をbaseにする#68の兄弟PR。`20260827010000_block_persistence.sql`を含む |

推奨統合順は `#64 -> #66 -> #68/#69`。#68と#69は兄弟stacked PRなので、先に取り込んだPRを含むbaseへもう一方を載せ替え、最終差分とmigration順を再確認する。

## 機能別状況

| 機能 | 現行ブランチ | Draft統合後の見込み | 残作業 |
|---|---|---|---|
| 依頼CRUD | Postgres実装済み | 同左 | Production適用・接続確認 |
| 応募作成・辞退・一覧 | Postgres実装済み | 同左 | Production適用・接続確認 |
| 応募者選択・定員排他 | 未完成 | #64に原子操作あり | #64統合、競合テスト再実行 |
| マッチ詳細 | Memoryのみ | #64に実装あり | #64統合 |
| メッセージ一覧・送信・既読 | Memoryのみ | #64に実装あり | #64統合。カーソルページングは別途不足 |
| 完了確認・dispute | Memoryのみ | #64に実装あり | #64統合。72時間リマインドは別途不足 |
| 認証subjectからDB利用者への解決 | `ensure_user`で仮表示名を作成 | #68に実装あり | #68統合、実SuperTokensとの結合確認 |
| プロフィール取得・更新 | Memoryの共有store | #68に実装あり | #68統合 |
| ブロック・解除 | Postgres実装済み | 同左 | Production適用・接続確認 |
| 通報・高危険度依頼の停止 | Postgres実装済み | 同左 | 管理者による調査・解決・却下の状態遷移を追加 |
| 利用者設定 | Postgres実装済み | 同左 | Production適用・接続確認 |
| 依頼カード非表示 | Postgres実装済み | 同左 | Production適用・接続確認 |
| 依頼保存 | Postgres実装済み | 同左 | Production適用・接続確認 |
| 依頼構造化の監査情報 | Postgres実装済み | 同左 | 保持期間・管理画面の参照導線を決定 |
| レビュー | APIはMemory store | 未実装 | 投稿RPCまたはtransaction、当事者・完了状態検証、Repository、DBテスト |
| AI実績プロフィール | API・AIともモック、Memory store | 未実装 | Repository、生成履歴・本人承認・公開範囲の永続化、実AI境界 |
| 本人確認申請・審査 | APIは開発用モック、Memory store | 未実装 | Repository、審査状態遷移、担当者認可、監査ログ |
| 本人確認画像 | 未実装 | 未実装 | private Storage bucket、アップロード方式、短期署名URL、Storage policy、7日以内の削除job |
| 通報 | Postgres実装済み | 同左 | 管理者処理（調査・解決・却下）のRepository、API、DBテスト |
| Realtime chat | pollingのみ | 未実装 | Realtime購読権限、認証連携、再接続・重複排除テスト。書き込みはFastAPI経由を維持 |
| 管理画面向け操作 | 未実装 | 未実装 | 通報調査、利用停止、本人確認審査、監査ログ閲覧のAPI／DB認可 |

## baselineに存在するが未完成の領域

`20260820000000_baseline.sql`には、`messages`、`reviews`、
`achievement_profiles`、`verification_requests`、`reports`、`audit_logs`、
`user_blocks`のテーブルとRLSがある。メッセージとブロックは後続migrationおよび
FastAPIのPostgres Repositoryまで実装済みだが、レビュー、実績、本人確認には
業務状態遷移を原子的に実行するRPC、エラー変換、結合テストが不足する。通報は作成と
高危険度依頼の停止まで実装済みで、管理者処理が残る。

特に次の条件はテーブル単体の制約だけでは満たせないため、RPCまたは同一transaction内での
検証が必要である。

- レビュー対象がcompletedマッチの相手当事者であること。
- 通報対象が実在し、high risk依頼の停止と監査ログが同時に保存されること。
- 本人確認の承認・否認、利用者状態更新、削除期限、監査ログが不整合にならないこと。
- AI実績が完了済み活動を根拠にし、本人承認前にpublicにならないこと。

## Draft統合後も不足するSupabase作業

優先度の目安は、既に画面またはAPIが使うMemoryデータの消失防止を先にする。

1. レビューとAI実績プロフィールの永続化。
2. 本人確認審査とprivate Storage、署名URL、削除job。
3. 通報の管理者処理、利用停止、監査ログの永続化。
4. Supabase Realtimeの読み取り認可と再接続設計。
5. 構造化監査情報の保持期間の決定。
6. メッセージ等のカーソルページング、完了確認の72時間リマインドなど運用処理。

## 統合・完了条件

- Draftを最新`main`へ載せ替え、stacked PR由来の重複差分を除く。
- migrationは既存ファイルを書き換えずforward-onlyで適用する。
- `.venv/bin/python -m pytest -q`と`supabase/tests/run.sh`を成功させる。
- MemoryとPostgresでAPI契約、認可、状態遷移、409等のエラーが一致することを確認する。
- `tetote_app`をNOBYPASSRLSのまま使用し、actor contextなしの業務操作を拒否する。
- Production Supabaseへの適用前にバックアップ、適用順、rollback用corrective migration方針を確認する。

## 既存資料とのずれ

- `todo.md`と`docs/cross-team-coordination.md`では応募者選択・マッチ・チャットが未永続化とされているが、Draft #64には実装候補がある。merge前なので現行判定は未完成のままとする。
- `docs/api-development.md`の「依頼以外はインメモリ」という説明は、現行コードでは応募Postgres Repositoryが存在するため古い。
- 現在のブランチには利用者設定、依頼非表示、依頼保存のAPIが追加されているが、いずれもMemory Repositoryのみである。
