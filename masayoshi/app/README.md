# たすけの輪 FastAPI 開発ガイド

地域の困りごとと支援者をつなぐAPIである。現在はインメモリデータを使い、認証・AI・本人確認・DBを模擬している。

## セットアップと起動

リポジトリの `masayoshi` ディレクトリで実行する。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m uvicorn main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`
- ヘルスチェック: `http://localhost:8000/health`

`/requests` と `/api/requests` のように、各APIは `/api` 接頭辞の有無に対応する。

## フォルダ構成

```text
masayoshi/
├── main.py              # uvicorn用エントリーポイント
├── app/
│   ├── main.py          # ASGIアプリの公開
│   ├── cruds/main.py    # エンドポイントとインメモリCRUD
│   ├── routers/main.py  # システム系ルーター
│   └── schemas/main.py  # Pydantic入力スキーマ
└── tests/main.py        # APIテスト
```

入力項目を変更するときは `schemas/main.py`、APIや状態遷移を変更するときは `cruds/main.py`、ヘルスチェックなどのシステム系APIは `routers/main.py` を編集する。

## 主要エンドポイント

| Method | Path | 説明 |
|---|---|---|
| GET | `/health` | ヘルスチェック |
| GET / PATCH | `/profile` | プロフィール取得・更新 |
| POST | `/requests/structure` | 依頼文の構造化 |
| GET / POST | `/requests` | 依頼一覧・作成 |
| GET / PATCH / DELETE | `/requests/{id}` | 依頼取得・更新・取消 |
| POST | `/requests/{id}/applications` | 依頼への応募 |
| GET | `/requests/{id}/applications` | 応募者一覧 |
| POST | `/applications/{id}/select` | 応募者選択 |
| POST | `/applications/{id}/withdraw` | 応募取り下げ |
| GET / POST | `/matches/{id}/messages` | チャット取得・送信 |
| POST | `/matches/{id}/complete` | 完了確認 |
| POST | `/matches/{id}/dispute` | 異議申立て |
| POST | `/matches/{id}/reviews` | 評価投稿 |
| POST | `/achievements/generate` | 実績生成 |
| POST | `/verifications` | 本人確認申請 |
| POST | `/reports` | 通報 |
| POST | `/users/{id}/block` | ブロック・解除 |

詳細なリクエスト・レスポンス仕様はSwagger UIを参照する。

## 開発とテスト

```bash
python -m pytest -q
```

モックデータを初期状態へ戻す場合は次を実行する。

```bash
curl -X POST http://localhost:8000/_mock/reset
```

データはプロセス内だけに保存され、サーバーを再起動すると初期化される。本番環境では認証、認可、永続DB、CSRF対策、レート制限を本実装へ置き換えること。
