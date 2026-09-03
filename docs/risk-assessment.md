# 依頼の危険度判定

要件定義書 11.2、3.4、F-01、F-09 と Issue #30 に対応する。
実装は `app/services/safety.py`、テストは `tests/test_safety.py` にある。

## 1. 判定の順序

1. 個人情報マスクを適用する（`mask_request_text`）。
2. マスク済みテキストへ固定ルールを適用する。
3. 固定ルールが `prohibited` を出した場合、**LLMを呼ばずに**判定を確定する。
4. それ以外はマスク済みテキストだけをLLMへ渡す。
5. 固定ルールとLLMのうち**強い方**を最終危険度とする。

LLMへ渡すのはマスク済みテキストだけで、元の入力は渡さない。
固定ルールをLLMより先に確定させているため、LLMの応答だけで禁止判定を解除できない。

## 2. 危険度と決定

| `riskLevel` | `decision` | 処理 |
|---|---|---|
| `low` | `publish` | 通常公開できる |
| `medium` | `publish_with_warning` | 注意事項を添えて公開する |
| `high` | `pending_review` | 公開せず管理者審査へ送る |
| `prohibited` | `rejected` | 投稿を拒否する（HTTP 422） |

`riskLevel` は要件定義書 11.2 の語彙をそのまま使う。Issue #30 が挙げる
`review_required` は `decision: "pending_review"` が担う。
Issue #30 の「`high` は公開を拒否する」は、本実装では最上位の `prohibited` が担当する。
この対応関係は COORD-003 として `docs/cross-team-coordination.md` に記録し、
フロントエンド担当と表示文言を合意するまで暫定とする。

## 3. 固定ルール（`safety-rules-v1`）

要件定義書 3.4「MVP対象外」を禁止、11.2 が挙げる検査観点を審査対象として扱う。

### 禁止（`prohibited` → 投稿拒否）

| 理由コード | 対象 |
|---|---|
| `PROHIBITED_MEDICAL_CARE` | 医療行為、介護、看護、服薬、入浴介助など |
| `PROHIBITED_ELECTRICAL_WORK` | 電気工事、配線工事、分電盤など |
| `PROHIBITED_HEIGHT_WORK` | 高所、屋根、はしご、脚立など |
| `PROHIBITED_DANGEROUS_TOOL` | チェーンソー、草刈り機、溶接、高圧洗浄機など |
| `PROHIBITED_MONEY_HANDLING` | 金銭管理、通帳、暗証番号、振込、立て替えなど |
| `PROHIBITED_TRANSPORT` | 送迎、車で送る、運転など |
| `PROHIBITED_SHOPPING_PROXY` | 買い物代行、代理購入など |

### 審査対象（`high` → 管理者審査）

| 理由コード | 判定条件 |
|---|---|
| `REVIEW_LICENSE_REQUIRED` | 有資格、施工、解体、配管工事、ガス工事などの語 |
| `REVIEW_HEAVY_LIFTING` | 冷蔵庫、洗濯機、タンスなどの語、または **20kg以上** の重量表現 |
| `REVIEW_LATE_NIGHT` | 深夜、夜中などの語、または `scheduledAt` が **22:00〜05:59** |

境界値は「20kg以上」「22:00以上または06:00未満」であり、`19kg` と `21:00` は審査対象にしない。
`scheduledAt` の時刻はタイムゾーン付きの表記どおりの時刻（現地時刻）で判定する。
解析できない日時は危険側へ倒さず、入力形式の検証はスキーマの責務とする。

全角数字と全角英字は照合前に半角へ正規化するため、`２０ｋｇ` も検出できる。

## 4. LLM判定の扱い

| `llmStatus` | 発生条件 | 最終判定への影響 |
|---|---|---|
| `ok` | LLMが有効な `riskLevel` を返した | 固定ルールと比べて強い方を採用する |
| `skipped_fixed_rule` | 固定ルールで禁止が確定した | LLMを呼ばない |
| `skipped_not_configured` | LLM未設定の開発環境 | 判定へ影響しない |
| `unavailable` | 呼び出しが例外で失敗した | `high` へ引き上げ、`LLM_UNAVAILABLE` を付ける |
| `invalid_output` | `riskLevel` が語彙外だった | `high` へ引き上げ、`LLM_INVALID_OUTPUT` を付ける |

LLMが `prohibited` を返した場合も `high`（管理者審査）までに留める。
禁止は固定ルールだけが宣言できる。

`skipped_not_configured` は開発環境向けの挙動である。本番では
`GEMINI_API_KEY` を設定した判定クライアントを `configure_safety_llm_client()` で
差し込むことを前提とし、未設定のまま本番運用しないこと。

## 5. 監査

判定結果には次を含める。`SafetyAssessment.to_payload()` が生成する。

| フィールド | 内容 |
|---|---|
| `riskLevel` / `decision` | 最終判定と公開可否 |
| `reasonCodes` | 判定理由のコード一覧 |
| `messages` | 利用者向けの安全なメッセージ |
| `matchedRules` | 一致した固定ルールのコード |
| `ruleVersion` | 固定ルールの版（`safety-rules-v1`） |
| `promptVersion` | プロンプトの版（`safety-llm-v1`） |
| `model` | 判定に使ったモデル名 |
| `llmLevel` / `llmStatus` | LLM単独の判定と実行結果 |
| `evaluatedAt` | 判定日時（ISO 8601、UTC） |

ルールを変更したときは `RULE_VERSION` を、プロンプトを変更したときは
`PROMPT_VERSION` を上げる。過去の判定がどの版で行われたか追跡できなくなるため、
版を据え置いたまま内容だけを変更しない。

## 6. APIへの反映

### `POST /requests/structure`

- 禁止判定は `422 PROHIBITED_REQUEST` を返す。`details` に `reasonCodes` と `messages` を含める。
- 禁止でなければレスポンスへ `safety` を含める。構造化結果は従来どおり自動公開しない。

### `POST /requests`

- `title` と `description` をマスクしてから判定し、`scheduledAt` を時間帯判定へ使う。
- 禁止判定は `422 PROHIBITED_REQUEST` で作成しない。
- `pending_review` 相当は作成した上で状態を `pending_review` にし、公開しない。
- `riskLevel` はサーバー側の判定結果で保存する。**クライアントが送る `riskLevel` は採用しない。**
- 判定メッセージは `warnings` として返す。

### `PATCH /requests/{request_id}`

- `title`、`description`、`scheduledAt` のいずれかを変更する場合だけ再判定する。
  作成時の判定を更新で迂回できないようにするためである。
- 禁止判定になる変更は `422 PROHIBITED_REQUEST` で拒否する。
- 審査対象になる変更は適用したうえで状態を `pending_review` にする。
- 保存済みの `riskLevel` は更新しない。Postgres の `app.update_request` がこの列を
  受け取らず、Memory実装とだけ差が出るためである。公開可否は `status` で止まる。
  列の更新は Supabase 担当との合意後に行う（COORD-003）。

## 7. テスト

```bash
.venv/Scripts/python -m pytest -q
```

`tests/test_safety.py` で次を検証する。

- 固定ルールがMVP対象外の作業を検出する
- 重量と時間帯の境界値（19kg/20kg、21:00/22:00/05:59/06:00）
- LLMが固定ルールの禁止・審査判定を緩められない
- LLMが危険度を引き上げられる
- LLM障害時と応答不正時に管理者審査へ送る
- 監査項目が判定結果に含まれる
- 各エンドポイントが判定に従って拒否・審査・公開を分ける
- 更新で禁止内容を持ち込めない
