# backend_mock

「たすけの輪」のフロントエンド開発用FastAPIモックである。

## セットアップ

```bash
cd masayoshi/backend_mock
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -e '.[dev]'
```

## 起動

```bash
uvicorn app.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

フロントエンドの環境変数例：

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## モックの初期化

```http
POST /_mock/reset
```

## 主なエンドポイント

| Method | Path | 用途 |
|---|---|---|
| GET | `/health` | ヘルスチェック |
| GET | `/profile` | ログインユーザー取得 |
| POST | `/requests/structure` | 依頼文のAI構造化モック |
| GET | `/requests` | 依頼一覧 |
| POST | `/requests` | 依頼作成 |
| GET | `/requests/{request_id}/applications` | 応募者一覧 |
| POST | `/applications/{application_id}/select` | 依頼者による応募者選択 |
| GET/POST | `/matches/{match_id}/messages` | チャット |
| POST | `/matches/{match_id}/complete` | 完了確認 |
| POST | `/matches/{match_id}/reviews` | 評価・感謝 |
| POST | `/achievements/generate` | AI実績生成モック |
| POST | `/reports` | 通報 |

## 注意

- 認証、AI、本人確認、DBは模擬である。
- データはプロセス内メモリに保存され、再起動すると初期化される。
- CORSはフロント開発用に全オリジンを許可している。
- 本番環境へ流用してはならない。
