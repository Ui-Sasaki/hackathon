# 依頼の公開と取消

依頼者が確認画面から依頼を出し、支援者の一覧に載せ、必要なら取り消すまでの状態遷移。

## 状態遷移

```
POST /requests              -> published（利用者が confirmed=true で送った依頼）
                            -> pending_review（危険度判定で審査対象になった依頼）
POST /requests/{id}/publish -> published（draft からのみ。本人のみ）
DELETE /requests/{id}       -> cancelled（本人のみ。completed / cancelled からは不可）
```

- 作成API は、利用者が確認済み（`confirmed: true`）の依頼を **そのまま公開** する。以前は draft で止まり、
  支援者の一覧（`GET /requests` は published のみ返す）に一度も載らなかった。
- 審査対象（`pending_review`）は管理者の判断待ちなので、本人が公開しようとすると `409 REQUEST_UNDER_REVIEW`。
- 公開済み・取消済みをもう一度公開しようとすると `409 INVALID_REQUEST_TRANSITION`。
- `POST /requests/{id}/publish` は、将来「下書き保存」を画面に足したときのために残している。

## 画面の流れ（tetote/）

1. `help/request-manual` または `help/request-voice` で内容を入力する。
2. `help/request-confirm` でマスキング確認 → AI整理 → 下書きを編集 → 「内容を確認して公開する」。
   作成API が公開まで行うので、画面は作成の成功をそのまま「公開しました」として扱ってよい。
3. `help/requests`（自分の依頼一覧）で内容の更新と取消ができる。
