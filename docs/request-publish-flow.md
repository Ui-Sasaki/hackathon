# 依頼の投稿・公開・取消フロー

依頼者が確認画面から依頼を出し、支援者の一覧に載せ、必要なら取り消すまでの流れ。

## 状態遷移

```
POST /requests            -> draft（危険度判定で審査対象なら pending_review）
POST /requests/{id}/publish -> published（draft からのみ。本人のみ）
DELETE /requests/{id}     -> cancelled（本人のみ。completed / cancelled からは不可）
```

- `pending_review` は管理者の判断待ちなので、本人が公開しようとすると `409 REQUEST_UNDER_REVIEW` を返す。
- 公開済みや取消済みをもう一度公開しようとすると `409 INVALID_REQUEST_TRANSITION`。
- 公開すると `version` が1つ進む。取消は現在の `version` を前提に行うため、同時操作は `409 REQUEST_STATE_CONFLICT` になる。

## 画面の流れ（tetote/）

1. `help/request-manual` または `help/request-voice` で内容を入力する。
2. `help/request-confirm` でマスキング確認 → 「AIで内容を整理する」 → 下書きを編集する。
3. 「この内容で依頼する」を押す。
   - `features/requests/submit.ts` の `buildCreateRequestInput` が下書きを作成APIの形に整える。
     AI が返さなかった所要時間・日時は、手入力画面で選んだ「必要な時間」「いつまで」のラベルから補い、無ければ 30分・3日後を使う。地域は下書きの `approximateArea`、無ければ `AREA-001`。
   - `submitAndPublishRequest` が `POST /requests` → `POST /requests/{id}/publish` を続けて呼ぶ。審査対象（`pending_review`）なら公開は呼ばない。
4. `help/request-done` に移り、公開状態を伝える。
   - `published`: 支援者に公開された。
   - `pending_review`: 確認が終わると公開される。
   - `draft`: 保存はできたが公開に失敗した。
5. 「この依頼を取り消す」→「はい、取り消す」の2段階で `DELETE /requests/{id}` を呼ぶ。成功すると「依頼を取り消しました」を表示する。

## 未接続の範囲

- 依頼者が過去に出した依頼の一覧・詳細画面はまだ無い。取消は完了画面からのみ行える（Issue #84 の「更新」は未対応）。
- Postgres 実装の `set_status` は `app.set_request_status` を使うため、公開遷移も既存の関数で動く。RLS で本人以外が更新できないことは Supabase 担当の設定に依存する。
