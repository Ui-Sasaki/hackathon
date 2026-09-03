# 通報・ブロックのフロントエンド接続

Issue #87、TODO 30〜31 に対応する。要件定義書 F-09（通報・ブロック）を前提とする。

実装は `tetote/src/features/safety/`（API接続と純粋な状態関数）、
`tetote/src/context/SafetyContext.tsx`（ブロック状態の共有）、
`tetote/src/shared/ReportScreen.tsx`（通報・ブロック画面）。
バックエンドは既存の `POST /reports` と `POST /users/{user_id}/block` をそのまま使う。

## 1. 送るもの・送らないもの

| 操作 | 送る | 送らない（サーバーが決める） |
|---|---|---|
| 通報 `POST /reports` | `targetType`、`targetId`、`reason`、`description` | 通報者ID、`severity`、`status`、日時 |
| ブロック／解除 `POST /users/{id}/block` | `blocked: true/false` | 操作者ID |

通報の `description` はサーバーと同じ 10〜2000 文字の条件を画面側でも先に検証する。

## 2. 画面の流れ

```
応募画面（helper/request）
  └「この依頼を通報する・依頼者をブロックする」
        └ /helper/report?targetType=request&targetId=…&title=…
              ├ 理由（8択）＋状況（自由記述）→ 通報を送る → 受付表示
              └ 依頼者をブロック／解除（依頼者IDは GET /requests/{id} から取得）
```

`/help/report` からも同じ画面を開ける（依頼者側が支援者を通報する場合は `targetUserId` を渡す）。

## 3. 状態と表示

| 状況 | 表示 |
|---|---|
| 送信中 | ボタンにインジケータ、二重送信不可 |
| 受付（`severity: high`） | 「危険性が高い内容のため、この依頼は一時的に非公開になります」 |
| 受付（`severity: medium`） | 「運営が確認します」 |
| 401 / 403 / 404 / 409 / 422 / 通信失敗 | `safetyErrorMessage()` が利用者向けの一文へ変換。「もう一度送る」で再試行 |
| 自分自身をブロック | ボタンを出さず「自分自身はブロックできません」。サーバーの 422 `SELF_BLOCK_NOT_ALLOWED` も同じ文言へ変換 |

## 4. ブロック後の除外

- ブロック関係は `SafetyProvider` がセッション内に保持し、`withoutBlocked(items, ownerOf)` で一覧から除外できる。
- サーバー側も同じ関係を保存し、依頼一覧・詳細・応募・メッセージを非表示にする（詳細は 404 で存在を伏せる）。
  画面側の除外は「再読み込み前の即時反映」のためで、正本はサーバーである。
- ブロック一覧を返すAPIがまだ無いため、再読み込み後の画面側の状態は空に戻る。サーバー側の非表示は継続する。

## 5. テスト

```bash
cd tetote && npm test
```

| ファイル | 対象 |
|---|---|
| `features/safety/client.test.ts` | 送信項目の限定、ブロック／解除、依頼者IDの取得、401〜422・通信失敗の文言変換 |
| `features/safety/blocking.test.ts` | 自己ブロック防止、重複操作の冪等性、対象除外 |

ローカルのExpo Webビルド＋FastAPI（認証モック）で、通報（高危険度→依頼が非公開になる）、
ブロック（一覧から相手の依頼が消える・詳細が404）、解除の3操作を通しで確認済み。
