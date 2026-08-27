# チーム開発規則

## 適用範囲

- このファイルはリポジトリ全体に適用する。
- 実装前に `要件定義書.md` と `docs/fastapi-coding-standards.md` の関連箇所を確認する。
- 指示が競合する場合は、ユーザーの依頼、より深い階層の `AGENTS.md`、このファイルの順で優先する。

## リポジトリ構成

- アプリはリポジトリ直下の `app/`、テストは `tests/` に置く。
- 個人名やブランチ名のトップレベルディレクトリを作らない。作業の分離には Git ブランチを使う。
- キャッシュ、仮想環境、秘密情報、生成物をコミットしない。
- ファイル移動時は README、import、テスト、設定内の古いパスも同時に更新する。

## Git と変更管理

- 1ブランチ・1Pull Requestを1つの目的に絞り、無関係な変更を混ぜない。
- 作業前と完了前に `git status --short` を確認し、他メンバーの未コミット変更を保持する。
- 既存変更の上書き、履歴の書き換え、強制pushを無断で行わない。
- 公開API、データ形式、依存関係の破壊的変更は、影響と移行方法をPull Requestに記載して合意を得る。
- コミットメッセージには、何をしたかが分かる命令形の要約を使う。

## 実装

- 要件とIssueの受け入れ条件を、変更前に確認できるチェック項目へ分解する。
- 差分を必要最小限に保ち、既存の責務分担と命名に従う。
- 認証・認可、入力検証、個人情報、秘密情報、状態遷移を変更時の必須確認項目とする。
- 振る舞いを変更したら対応するテストとドキュメントを同じ変更に含める。
- 詳細なPython/FastAPI規約は `docs/fastapi-coding-standards.md` に従う。

## Supabaseを担当しないバックエンド開発の境界

- SupabaseまたはPostgreSQLを担当しない作業では、実装範囲をFastAPIエンドポイント、Pydanticスキーマ、Service、Repositoryの共通インターフェース、Memory Repository、対応するAPIテストまでとする。
- `Postgres*Repository`、`app/db.py`、`supabase/migrations/`、`supabase/tests/`、RLS、DBロール、PostgreSQL関数および本番DB接続設定は、Supabase担当者との合意なしに変更しない。
- 永続化が必要な機能では、先にRepositoryの入出力と業務上必要な操作を定義し、Memory RepositoryでAPIの振る舞いとテストを完成させる。Postgres実装を空または暫定実装のまま本番で選択可能にしない。
- Supabase担当者へ引き継ぐ際は、追加したRepositoryメソッド、入出力、認可条件、状態遷移、期待するエラー、Memory RepositoryとAPIテストの場所を共有する。
- 既存のPostgres実装やmigrationに未解決の競合がある場合、競合解消の担当者でなければ変更を重ねず、Serviceや新規ファイルへ分離して作業する。

## FastAPI担当とフロントエンドの境界

- FastAPI担当者は、FastAPIのAPI契約、認証・認可、入力検証、業務ルール、状態遷移、エラーコード、Service、Repository境界、Memory Repository、APIテストに加え、`tetote/`からFastAPIへのAPI接続も担当する。
- API接続には、共通APIクライアント、認証Cookieとanti-CSRF、固定モックからAPIレスポンスへの置換、IDとversionの維持、loading・empty・error・再試行・競合状態の反映、接続テストを含める。
- API接続に必要な範囲では`tetote/`を変更できるが、既存の画面デザイン、レイアウト、スタイル、導線および操作感を必要以上に変更しない。
- 画面デザイン、レイアウト、スタイル、アニメーション、`PanResponder`、端末固有UI、API接続と無関係なReact hooksやlint修正はフロントエンド担当者の責務として追わない。
- API変更によるフロントエンドへの影響と接続方法を記録し、FastAPIと接続側のテストを同じ責務単位で完成させる。

## 検証とレビュー

- 読み取り、状態確認、差分確認、ログ確認、テストやビルドなど、外部状態を変更しない確認・検証は都度ユーザーの許可を求めず実行する。
- Vercel対象のPRブランチには、最新`main`の`tetote/`と`tetote/vercel.json`を取り込み、`tetote/`で`npm ci`と`npx expo export --platform web`が成功することを確認する。
- Vercelチェックが失敗した場合は、成功しているPRとの差分、対象ブランチの`tetote/`有無、Vercel設定、ビルドログの順に確認し、コードや設定の問題とアカウント権限の問題を切り分ける。
- 変更箇所に近いテストを先に実行し、完了前に `.venv/bin/python -m pytest -q` を実行する。
- テストを実行できない場合は、未検証の範囲と理由を明記する。
- レビューでは、要件逸脱、バグ、セキュリティ、互換性、テスト不足を優先し、重大度と対象箇所を示す。
- Pull Requestには目的、主な変更、検証結果、既知の制約を記載する。
