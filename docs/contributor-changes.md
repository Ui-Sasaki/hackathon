# 他コントリビューター変更リファレンス

## 目的と使い方

この文書は、別ブランチや別Pull Requestで導入された設計上の前提を、実装とレビューで見落とさないためのローカル参照資料である。変更内容を自然言語で要約し、コードを読む際の入口として使う。

- 実装前に、変更対象と関係する記録を読む。
- レビュー時は末尾の「レビュー時の照合事項」を確認する。
- この文書はコードやPull Requestの代替ではない。食い違う場合は、対象ブランチの実コード、マージ済みPull Request、要件定義の順に確認し、この文書を更新する。
- 新しい変更を追記するときは、確認日、作成者、Pull Requestまたはコミット、影響範囲、既知の制約を記録する。
- メールアドレス、トークン、環境変数の値などの秘密情報や個人情報は記録しない。

## 2026-08-22時点の変更

### Ui-Sasaki: Expoオンボーディング画面とVercelルーティング

出典は [PR #49 FRONTEND #1 (ONBOARDING)](https://github.com/Ui-Sasaki/hackathon/pull/49) と [PR #50 Fix Vercel Expo routes](https://github.com/Ui-Sasaki/hackathon/pull/50) で、いずれも`main`へマージ済みである。

`tetote/`にExpo Routerを使うフロントエンドが追加された。オンボーディングは、導入、利用目的の選択、依頼者プロフィール、支援者プロフィール、支援カテゴリや表示設定、キャラクター選択という複数画面で構成される。画面状態をまとめるための`OnboardingContext`も配置されている。VercelではExpoのWeb出力からクライアントサイドルーティングできるよう、`tetote/vercel.json`が追加された。

現状のオンボーディングはUI実装が中心である。各入力画面は主に画面ローカルの`useState`を使い、Contextへの集約、SuperTokensによる認証、FastAPIへの送信、Supabaseへの保存、オンボーディング完了判定は接続されていない。最終画面もAPI保存ではなくルート画面への遷移を行う。そのため、API連携を追加する変更では既存画面遷移を保ちつつ、Contextへの集約、エラー表示、送信中状態、再試行、完了後の遷移を明示的に設計する必要がある。

レビューでは、`tetote/`を消したり別のトップレベルへ複製していないこと、Expo RouterのパスとVercel rewriteが一致すること、オンボーディング入力が画面遷移で失われないこと、API成功前に完了扱いにしていないことを確認する。

### CoderK-star: Supabase基盤、RLS、依頼APIのPostgres永続化

出典は [PR #23 役割の語彙を利用者種別と文脈上のアクターに分離する](https://github.com/Ui-Sasaki/hackathon/pull/23)、[PR #24 Supabase永続化の基盤スキーマ・制約・RLSを用意する](https://github.com/Ui-Sasaki/hackathon/pull/24)、[PR #25 依頼作成・取得・更新・取消APIをSupabaseへ接続する](https://github.com/Ui-Sasaki/hackathon/pull/25) で、いずれも`main`へマージ済みである。

利用者の永続ロールは`member`、`admin`、`verifier`である。`requester`と`helper`はアカウントを固定分類するロールではなく、依頼やマッチに対する文脈上の立場として扱う。したがって、オンボーディングで「手伝ってほしい」「手伝いたい」を選んでも、認可ロールを`requester`または`helper`として保存してはならない。

Supabaseには業務テーブル、制約、インデックス、RLSが導入されている。ランタイムはRLSを迂回しない`tetote_app`ロールを使い、各トランザクションで`app.actor_id`を設定する。SuperTokensの利用者IDと内部UUIDの対応は`app.ensure_user()`が担当する。テーブルをまたぐ認可や状態変更には、権限を限定した`SECURITY DEFINER`関数を使う箇所がある。新しいDB処理がService Roleや広すぎる権限でRLSを迂回したり、接続単位でアクター状態を残したりしないよう注意する。

依頼の作成・取得・更新・取消は、Memory/Postgresを差し替えられるRepository構成へ発展している。DBアクセスをエンドポイントへ直接追加せず、既存Repositoryと`actor_connection()`の責務を維持する。内部UUID、正確な座標、`original_text`など、公開契約にない値をレスポンスへ漏らしてはならない。

既知の制約として、すべての業務機能がPostgresへ永続化されているわけではない。プロフィール、オンボーディング完了状態、画像保存などを追加する場合は、「既にSupabase対応済み」と仮定せず、Repository、マイグレーション、RLS、APIテストを一体で追加する。

## レビュー時の照合事項

関連しない項目を機械的に要求するのではなく、レビュー対象の差分と接点がある項目を確認する。

- [ ] 対象差分に関係する上記の変更内容と、出典PRの実コードを確認した。
- [ ] `requester`／`helper`を永続的なアカウントロールとして再導入していない。
- [ ] DBアクセスが既存Repositoryとトランザクション単位のアクター設定を維持し、RLSを迂回していない。
- [ ] 公開APIへ内部ID、秘密情報、個人情報、正確な位置情報を追加していない。
- [ ] `tetote/`のExpo Router構成とVercel設定を壊していない。
- [ ] オンボーディング関連では、入力保持、認証、API保存、完了判定、失敗時の挙動が一貫している。
- [ ] 既存の前提を意図的に変更する場合、Pull Requestに理由、影響範囲、移行方法、検証結果がある。
- [ ] 新しい他コントリビューター変更を確認した場合、この文書へ出典と確認日を追記した。
