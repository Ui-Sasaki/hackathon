# 他コントリビューター変更リファレンス

## 目的と使い方

別ブランチやPull Requestで導入された設計上の前提を実装・レビューで維持するための参照資料である。記録と実装が異なる場合は、対象ブランチの実コードとマージ済みPull Requestを正とする。

## 2026-08-25確認の変更

### Supabase基盤と依頼Repository

出典は [PR #23](https://github.com/Ui-Sasaki/hackathon/pull/23)、[PR #24](https://github.com/Ui-Sasaki/hackathon/pull/24)、[PR #25](https://github.com/Ui-Sasaki/hackathon/pull/25) で、いずれも`main`へマージ済みである。

永続ロールは`member`、`admin`、`verifier`であり、`requester`と`helper`は依頼に対する文脈上の立場として扱う。DBアクセスはRepositoryと`actor_connection()`へ閉じ込め、RLSを迂回しない。内部UUID、正確な座標、本人確認メタデータなど公開契約にない値をレスポンスへ含めない。

### OpenAPI契約と応募Repository

出典は [PR #48 OpenAPI契約を整備](https://github.com/Ui-Sasaki/hackathon/pull/48) で、`main`へマージ済みである。

FastAPIの公開レスポンスモデル、エラー例、OpenAPIの決定的な書き出しと一致テストが追加された。応募処理もMemory/Postgresを差し替えられるRepositoryとServiceへ分離されている。API変更時は`docs/openapi.json`を再生成し、依頼・応募両Repositoryの依存性注入とリセット処理を維持する。

### 依頼者・支援者UI

出典は [PR #49](https://github.com/Ui-Sasaki/hackathon/pull/49)、[PR #50](https://github.com/Ui-Sasaki/hackathon/pull/50)、[PR #53 Help & helper side](https://github.com/Ui-Sasaki/hackathon/pull/53) で、いずれも`main`へマージ済みである。

`tetote/`にはExpo Routerを使うオンボーディングと、依頼者側`help/`・支援者側`helper/`の画面がある。フロント変更時は両利用文脈のルーティング、共通設定・プロフィール画面、`tetote/vercel.json`を維持する。

## レビュー時の照合事項

- [ ] `requester`／`helper`を永続的なアカウントロールとして再導入していない。
- [ ] DBアクセスがRepositoryとトランザクション単位のアクター設定を維持している。
- [ ] 公開APIへ内部ID、秘密情報、正確な位置情報、本人確認メタデータを追加していない。
- [ ] 応募Repositoryと依頼Repositoryの依存性注入・リセット処理を維持している。
- [ ] OpenAPIの生成物と実装が一致している。
- [ ] `tetote/`のExpo Router構成とVercel設定を壊していない。
